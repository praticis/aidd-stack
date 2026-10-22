#!/usr/bin/env bash
# The atlas MCP's queries and the graph writer against a real Neo4j. A store that is faked runs no Cypher, so a query
# that reads the graph wrongly passes every other test, and the corpus and the micro set compare dry-runs, which never
# reach the writer. This starts a throwaway Neo4j on its own network, applies the schema, indexes the repositories under
# tests/mcp_it (a Go service on two branches, an ASP.NET one, and a TS client of both) and leaves a dry-run of each
# snapshot. In a tenant of its own, the Go service is written with its branch's file, again without it, and once more at
# that commit, as the refresher does after an upgrade. Then tests/test_mcp_neo4j.py asks the tools, and
# tests/test_graph_writer_neo4j.py checks that the graph holds each dry-run. Nothing of an install is touched, and
# everything is removed at the end.
#
#   indexer/scripts/mcp-it.sh [pytest args]
set -euo pipefail

indexer="$(cd "$(dirname "$0")/.." && pwd)"
root="$(dirname "$indexer")"
image="${AIDD_INDEXER_IMAGE:-aidd-indexer:local}"
test_image="${AIDD_INDEXER_TEST_IMAGE:-aidd-indexer-test:local}"
neo4j_image="${AIDD_NEO4J_IMAGE:-neo4j:5.26.30-community}"
name="aidd-mcp-it-$$"
password="it-$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')"

cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker network rm "$name" >/dev/null 2>&1 || true
  docker volume rm "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create "$name" >/dev/null
docker volume create "$name" >/dev/null
docker run -d --name "$name" --network "$name" -e NEO4J_AUTH="neo4j/$password" "$neo4j_image" >/dev/null
for _ in $(seq 1 60); do
  docker exec "$name" cypher-shell -u neo4j -p "$password" "RETURN 1" >/dev/null 2>&1 && break
  sleep 2
done
docker exec -i "$name" cypher-shell -u neo4j -p "$password" <"$root/neo4j/init/schema.cypher" >/dev/null

env=(-e NEO4J_URI="bolt://$name:7687" -e NEO4J_USERNAME=neo4j -e NEO4J_PASSWORD="$password" -e NEO4J_DATABASE=neo4j)
docker run --rm --network "$name" "${env[@]}" -e HOME=/tmp -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$indexer":/src:ro -v "$name":/dry -w /src --entrypoint sh "$image" -c '
set -e
T=it
idx() { python -m aidd_indexer.cli index "$@" --tenant "$T" >/dev/null 2>&1 || python -m aidd_indexer.cli index "$@" --tenant "$T"; }
dry() { idx "$1" --dry-run --out "/dry/${T}__$(basename "$1")__$(git -C "$1" branch --show-current | tr / _).json"; }
git_() { git -c user.name=it -c user.email=it@example.com -c commit.gpgsign=false "$@"; }
cp -R /src/tests/mcp_it /tmp/it
cd /tmp/it/orders && git_ init -q -b main && git_ add go.mod main.go && git_ commit -qm orders
git_ checkout -qb feature/items && git_ add items.go && git_ commit -qm items
idx /tmp/it/orders --ephemeral && dry /tmp/it/orders
git_ checkout -q main && idx /tmp/it/orders && dry /tmp/it/orders
cd /tmp/it/accounts && git_ init -q -b main && git_ add -A && git_ commit -qm accounts && idx /tmp/it/accounts && dry /tmp/it/accounts
cd /tmp/it/shop && git_ init -q -b main && git_ add -A && git_ commit -qm shop && idx /tmp/it/shop && dry /tmp/it/shop
T=it-writer
mkdir /tmp/w && cp -R /src/tests/mcp_it/orders /tmp/w/orders && cd /tmp/w/orders
git_ init -q -b main && git_ add -A && git_ commit -qm orders && idx /tmp/w/orders
git_ rm -q items.go && git_ commit -qm "no items" && idx /tmp/w/orders && idx /tmp/w/orders && dry /tmp/w/orders
'
docker run --rm --network "$name" "${env[@]}" -e AIDD_TENANT=it -e AIDD_IT_DRY=/dry -e PYTHONPATH=/src \
  -e PYTHONDONTWRITEBYTECODE=1 -v "$indexer":/src:ro -v "$name":/dry:ro -w /src --entrypoint python "$test_image" \
  -m pytest -q -p no:cacheprovider tests/test_mcp_neo4j.py tests/test_graph_writer_neo4j.py "$@"
