#!/usr/bin/env bash
#
# install-check.sh — Health check for the aidd-stack local infrastructure.
# Verifies, in order: .env contract → containers → Neo4j (auth, database,
# schema, APOC) → Qdrant → MCP endpoints. Prints one OK/FAIL line per check
# and exits non-zero if anything failed.
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

REQUIRED_VARS=(WORKSPACE_PATH OBSIDIAN_VAULT_PATH AIDD_TENANT NEO4J_USER NEO4J_PASSWORD NEO4J_DATABASE NEO4J_HEAP NEO4J_PAGECACHE)
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

for c in aidd-core-qdrant aidd-core-neo4j aidd-mcp-qdrant aidd-mcp-obsidian aidd-mcp-git aidd-mcp-neo4j; do
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

if curl -sf http://localhost:6333/collections > /dev/null; then
  cols="$(curl -s http://localhost:6333/collections | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | tr '\n' ' ')"
  ok "REST API up (collections: ${cols:-none yet})"
else
  fail "Qdrant REST not reachable on :6333"
fi

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
mcp_check "atlas"    "http://localhost:3004/mcp/"

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
