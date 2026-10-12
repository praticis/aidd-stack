#!/usr/bin/env bash
#
# install-check.sh — Health check for the aidd-stack local infrastructure.
# Verifies, in order: .env contract → containers → exposure (ports on localhost,
# gateway refusals) → Neo4j (auth, database, schema, APOC) → Qdrant (API key) →
# MCP endpoints → indexer → refresher. Prints one OK/FAIL line per check and
# exits non-zero if anything failed. Portable: bash 3.2 (macOS) and Linux/WSL.
#
# Usage:
#   ./setup/install-check.sh            # uses ~/.aidd/.env
#   AIDD_DIR=/other ./install-check.sh  # custom install dir
#

set -uo pipefail

AIDD_DIR="${AIDD_DIR:-$HOME/.aidd}"
ENV_FILE="$AIDD_DIR/.env"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; BOLD='\033[1m'; NC='\033[0m'
FAILS=0

ok()   { printf "  ${GREEN}[OK]${NC}   %s\n" "$1"; }
fail() { printf "  ${RED}[FAIL]${NC} %s\n" "$1"; FAILS=$((FAILS + 1)); }
warn() { printf "  ${YELLOW}[WARN]${NC} %s\n" "$1"; }
section() { printf "\n${BOLD}%s${NC}\n" "$1"; }

# ------------------------------------------------------------------------------
# Environment contract
# ------------------------------------------------------------------------------
section "Environment ($ENV_FILE)"

if [ ! -f "$ENV_FILE" ]; then
  fail ".env not found — run setup/install.sh first"
  exit 1
fi

# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a

REQUIRED_VARS=(WORKSPACE_PATH OBSIDIAN_VAULT_PATH AIDD_TENANT NEO4J_USER NEO4J_PASSWORD NEO4J_DATABASE NEO4J_HEAP NEO4J_PAGECACHE QDRANT_API_KEY)
for v in "${REQUIRED_VARS[@]}"; do
  if [ -n "${!v:-}" ]; then ok "$v is set"; else fail "$v is missing or empty"; fi
done

[ -d "${WORKSPACE_PATH:-/nonexistent}" ] && ok "WORKSPACE_PATH exists ($WORKSPACE_PATH)" || fail "WORKSPACE_PATH does not exist: ${WORKSPACE_PATH:-<unset>}"
[ -f "$AIDD_DIR/atlas.yaml" ] && ok "atlas.yaml present" || fail "atlas.yaml missing at $AIDD_DIR — install.sh writes it (step 4)"

# ------------------------------------------------------------------------------
# Containers
# ------------------------------------------------------------------------------
section "Containers"

if ! command -v docker &> /dev/null; then
  fail "docker not found in PATH"; exit 1
fi

container_state() { docker inspect -f '{{.State.Status}}' "$1" 2>/dev/null || echo "missing"; }
container_health() { docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' "$1" 2>/dev/null || echo "missing"; }
container_exit() { docker inspect -f '{{.State.ExitCode}}' "$1" 2>/dev/null || echo "?"; }

for c in aidd-core-qdrant aidd-core-neo4j aidd-mcp-qdrant aidd-mcp-obsidian aidd-mcp-git aidd-mcp-atlas aidd-mcp-gateway aidd-refresher; do
  state="$(container_state "$c")"; health="$(container_health "$c")"
  if [ "$state" = "running" ] && { [ "$health" = "healthy" ] || [ "$health" = "n/a" ]; }; then
    ok "$c running${health:+ ($health)}"
  else
    fail "$c state=$state health=$health  → docker logs $c"
  fi
done

state="$(container_state aidd-neo4j-init)"; code="$(container_exit aidd-neo4j-init)"
if [ "$state" = "exited" ] && [ "$code" = "0" ]; then
  ok "aidd-neo4j-init exited 0 (schema applied)"
elif [ "$state" = "missing" ]; then
  fail "aidd-neo4j-init never ran — docker compose up did not reach it"
else
  fail "aidd-neo4j-init state=$state exit=$code  → docker logs aidd-neo4j-init"
fi

# ------------------------------------------------------------------------------
# Exposure — nothing reachable from the network; MCPs only through the gateway
# ------------------------------------------------------------------------------
section "Exposure"

bind="${AIDD_BIND_ADDRESS:-127.0.0.1}"
for c in aidd-core-qdrant aidd-core-neo4j aidd-mcp-gateway; do
  ports="$(docker port "$c" 2>/dev/null)"
  [ -n "$ports" ] || continue
  open="$(echo "$ports" | grep -E '0\.0\.0\.0:|\[::\]:|:::' || true)"
  if [ -z "$open" ]; then ok "$c publishes on localhost only"
  elif [ "$bind" != "127.0.0.1" ]; then warn "$c publishes on all interfaces (AIDD_BIND_ADDRESS=$bind)"
  else fail "$c publishes on all interfaces: $(echo "$open" | tr '\n' ' ') — recreate: cd $AIDD_DIR && docker compose up -d"; fi
done
for c in aidd-mcp-qdrant aidd-mcp-obsidian aidd-mcp-git aidd-mcp-atlas; do
  [ -z "$(docker port "$c" 2>/dev/null)" ] && ok "$c not published (reached through the gateway)" || fail "$c publishes its own port — bypasses the gateway"
done
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:3005/mcp -H 'Host: rebind.example:3005' --max-time 5)"
[ "$code" = "403" ] && ok "gateway refuses a foreign Host (DNS rebinding)" || fail "gateway answered HTTP $code to Host: rebind.example — expected 403"
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:3005/mcp -H 'Origin: http://evil.example' --max-time 5)"
[ "$code" = "403" ] && ok "gateway refuses a foreign browser Origin" || fail "gateway answered HTTP $code to Origin: evil.example — expected 403"

# ------------------------------------------------------------------------------
# Neo4j
# ------------------------------------------------------------------------------
section "Neo4j (database: $NEO4J_DATABASE)"

cypher() {
  docker exec aidd-core-neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -d "$NEO4J_DATABASE" --format plain "$1" 2>&1
}

out="$(cypher 'RETURN 1 AS ok')"
if echo "$out" | grep -q '^1$'; then
  ok "authentication and database '$NEO4J_DATABASE' reachable"
else
  fail "cannot query '$NEO4J_DATABASE' as $NEO4J_USER: $(echo "$out" | head -1)"
  echo "         (password/database are fixed on first start of the volume — a re-created .env with an old"
  echo "          neo4j_data volume causes exactly this: cd $AIDD_DIR && docker compose down -v && docker compose up -d)"
fi

out="$(cypher 'SHOW DATABASES YIELD name, currentStatus WHERE name <> "system" RETURN name + ":" + currentStatus')"
echo "$out" | grep -q "^\"$NEO4J_DATABASE:online\"$" && ok "default database is '$NEO4J_DATABASE' and online" || fail "default database mismatch: $(echo "$out" | tr '\n' ' ')"

expected_constraints="$(grep -c '^CREATE CONSTRAINT' "$AIDD_DIR/neo4j/init/schema.cypher" 2>/dev/null || echo 14)"
out="$(cypher 'SHOW CONSTRAINTS YIELD name RETURN count(*)')"
n="$(echo "$out" | grep -E '^[0-9]+$' | head -1)"
[ "${n:-0}" -ge "$expected_constraints" ] && ok "$n constraints present (expected $expected_constraints)" || fail "constraints: ${n:-0} found, expected $expected_constraints"

out="$(cypher 'SHOW INDEXES YIELD name WHERE name = "symbol_fulltext" RETURN count(*)')"
echo "$out" | grep -q '^1$' && ok "full-text index symbol_fulltext present" || fail "symbol_fulltext index missing"

out="$(cypher 'RETURN apoc.version()')"
echo "$out" | grep -qE '^"?[0-9]+\.[0-9]+' && ok "APOC loaded ($(echo "$out" | tail -1 | tr -d '"'))" || fail "APOC not available: $(echo "$out" | head -1)"

out="$(cypher 'MATCH (n) RETURN count(n)')"
n="$(echo "$out" | grep -E '^[0-9]+$' | head -1)"
if [ "${n:-0}" = "0" ]; then warn "atlas is empty (expected until 'aidd index' exists — roadmap F0.3)"; else ok "atlas has $n nodes"; fi

# ------------------------------------------------------------------------------
# Qdrant
# ------------------------------------------------------------------------------
section "Qdrant"

if curl -sf -H "api-key: ${QDRANT_API_KEY:-}" http://localhost:6333/collections > /dev/null; then
  cols="$(curl -s -H "api-key: ${QDRANT_API_KEY:-}" http://localhost:6333/collections | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | tr '\n' ' ')"
  ok "REST API up with the API key (collections: ${cols:-none yet})"
else
  fail "Qdrant REST not reachable on :6333 with QDRANT_API_KEY"
fi
code="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:6333/collections --max-time 5)"
[ "$code" = "401" ] || [ "$code" = "403" ] && ok "Qdrant refuses requests without the API key" || fail "Qdrant answered HTTP $code without an API key — expected 401"

# ------------------------------------------------------------------------------
# MCP endpoints (JSON-RPC initialize handshake)
# ------------------------------------------------------------------------------
section "MCP endpoints"

mcp_check() {
  local name="$1" url="$2"
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$url" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"aidd-install-check","version":"0.1"}}}' \
    --max-time 10)"
  if [ "$code" = "200" ]; then
    ok "$name responds to initialize ($url)"
  elif [ "$code" = "000" ]; then
    fail "$name unreachable ($url)"
  else
    warn "$name answered HTTP $code to initialize ($url) — server up, check transport/path"
  fi
}

mcp_check "obsidian" "http://localhost:3001/mcp"
mcp_check "qdrant"   "http://localhost:3002/mcp/"
mcp_check "git"      "http://localhost:3003/mcp"
mcp_check "atlas"    "http://localhost:3005/mcp"

# atlas is ours: go one step further and call a real tool (stateless transport → a plain POST works).
atlas_body="$(curl -s -X POST http://localhost:3005/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"atlas_status","arguments":{}}}' --max-time 15)"
if echo "$atlas_body" | grep -q '"isError": *true'; then
  fail "atlas_status returned a tool error: $(echo "$atlas_body" | head -c 300)"
elif echo "$atlas_body" | grep -q '"tenant"'; then
  atlas_repos="$(echo "$atlas_body" | grep -o '\\"repo\\": *\\"[^\\]*' | sed 's/.*: *\\"//' | sort -u | tr '\n' ' ')"
  if [ -n "$atlas_repos" ]; then
    ok "atlas_status answers for tenant $AIDD_TENANT — repos: $atlas_repos"
  else
    warn "atlas_status answers but lists no repos — run: aidd bootstrap"
  fi
else
  fail "atlas_status did not answer as expected: $(echo "$atlas_body" | head -c 300)"
fi
health="$(curl -s --max-time 5 http://localhost:3005/healthz || true)"
case "$health" in
  *'"status":"ok"'*) ok "atlas /healthz ok (neo4j reachable from the MCP)";;
  "")                fail "atlas /healthz unreachable";;
  *)                 fail "atlas /healthz: $health";;
esac

# ------------------------------------------------------------------------------
# 5b. Indexer self-test (grammars + queries) — a broken image writes EMPTY snapshots
# ------------------------------------------------------------------------------
section "5b. Indexer self-test"
if ("$AIDD_DIR/aidd" selftest 2>&1 | sed 's/^/         /'; exit "${PIPESTATUS[0]}"); then
  ok "all tree-sitter grammars load inside the indexer image"
else
  fail "indexer self-test failed — rebuild: cd $AIDD_DIR && docker compose --profile tools build --no-cache indexer"
fi
if command -v cypher >/dev/null 2>&1 || true; then
  empty="$(docker exec aidd-core-neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -d "$NEO4J_DATABASE" --format plain \
    'MATCH (s:Snapshot) WHERE NOT (s)<-[:IN_SNAPSHOT]-(:File)-[:CONTAINS]->(:Symbol) RETURN count(s)' 2>/dev/null | grep -E '^[0-9]+$' | head -1)"
  if [ -n "$empty" ]; then
    [ "$empty" = "0" ] && ok "no snapshot without symbols" || fail "$empty snapshot(s) have files but zero symbols — indexed with a broken image? re-run: $AIDD_DIR/aidd bootstrap"
  fi
  # snapshots written by an older indexer are re-indexed by the next refresh (new extractors)
  stale="$(docker exec aidd-core-neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -d "$NEO4J_DATABASE" --format plain \
    "MATCH (s:Snapshot) WITH collect(DISTINCT s.indexer_version) AS v RETURN size(v)" 2>/dev/null | grep -E '^[0-9]+$' | head -1)"
  [ -n "$stale" ] && [ "$stale" -gt 1 ] && warn "snapshots from more than one indexer version — the next refresh re-indexes the older ones (or run: $AIDD_DIR/aidd refresh)"
  http="$(docker exec aidd-core-neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -d "$NEO4J_DATABASE" --format plain \
    "OPTIONAL MATCH (e:HttpEndpoint) WITH count(e) AS eps OPTIONAL MATCH (c:HttpCall) WITH eps, count(c) AS calls OPTIONAL MATCH ()-[x:CONSUMES]->() RETURN toString(eps) + ' ' + toString(calls) + ' ' + toString(count(x))" 2>/dev/null | tr -d '"' | grep -E '^[0-9]+ [0-9]+ [0-9]+$' | head -1)"
  if [ -n "$http" ]; then
    read -r eps calls consumes <<<"$http"
    if [ "$eps" = "0" ] && [ "$calls" = "0" ]; then
      warn "no HTTP endpoints / outbound calls in atlas yet — re-index after upgrading: $AIDD_DIR/aidd refresh"
    else
      ok "integration candidates: $eps HTTP endpoints exposed, $calls outbound calls recorded"
      if [ "$calls" != "0" ] && [ "$consumes" = "0" ]; then
        warn "outbound calls exist but no CONSUMES edge — the linker has not run (or nothing matched): $AIDD_DIR/aidd link"
      else
        ok "linker: $consumes CONSUMES edge(s) between services"
      fi
    fi
  fi
  deps="$(docker exec aidd-core-neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -d "$NEO4J_DATABASE" --format plain \
    "OPTIONAL MATCH ()-[d:DEPENDS_ON]->() RETURN count(d)" 2>/dev/null | grep -E '^[0-9]+$' | head -1)"
  [ -n "$deps" ] && ok "linker: $deps DEPENDS_ON edge(s) between services (internal packages from manifests)"
fi

# ------------------------------------------------------------------------------
# 6. Continuous update — the refresher container
# ------------------------------------------------------------------------------
section "6. Continuous update (refresher)"

token_file="${AIDD_GIT_TOKEN_FILE:-$AIDD_DIR/secrets/git-token}"
if [ -s "$token_file" ]; then
  perms="$(ls -l "$token_file" | cut -c1-10)"
  [ "$perms" = "-rw-------" ] && ok "read-only token present ($perms)" || warn "token file permissions are $perms — expected -rw------- (chmod 600 $token_file)"
else
  warn "no read-only token — the refresher follows your own fetches (paste one into $token_file, then: aidd schedule install)"
fi
interval="${AIDD_REFRESH_INTERVAL_MINUTES:-15}"
rows="$(docker exec aidd-core-neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -d "$NEO4J_DATABASE" --format plain \
  "MATCH (h:RefreshState) RETURN h.tenant + ' ' + toString(duration.inSeconds(h.last_finished_at, datetime()).seconds / 60) + ' ' + toString(h.last_rc)" 2>/dev/null \
  | tr -d '"' | grep -E '^[^ ]+ [0-9]+ -?[0-9]+$')"
if [ -z "$rows" ]; then
  warn "no refresh recorded in atlas yet (the refresher writes one per tenant after each run)"
else
  while read -r tenant age rc; do
    if [ "$age" -gt $(( interval * 2 )) ]; then fail "tenant $tenant: last refresh $age min ago (interval $interval min) — aidd schedule status"
    elif [ "$rc" != "0" ]; then fail "tenant $tenant: last refresh failed (rc=$rc) — aidd logs"
    else ok "tenant $tenant: last refresh $age min ago, rc=0"; fi
  done <<< "$rows"
fi
[ -x "$AIDD_DIR/aidd" ] && { "$AIDD_DIR/aidd" schedule check 2>/dev/null | sed 's/^/         /'; [ "${PIPESTATUS[0]}" -eq 0 ] || FAILS=$((FAILS + 1)); }

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
echo ""
if [ "$FAILS" -eq 0 ]; then
  printf "${GREEN}${BOLD}All checks passed.${NC}\n"
  echo "Next: open http://localhost:7474 (user $NEO4J_USER) and, in Claude Code, run /mcp to confirm 'atlas' is listed."
else
  printf "${RED}${BOLD}%d check(s) failed.${NC}\n" "$FAILS"
  exit 1
fi
