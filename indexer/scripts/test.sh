#!/usr/bin/env bash
# The indexer's tests in the test image (the indexer image plus pytest, and Node with a pinned TypeScript compiler, the
# reference TS's type cases are checked against), with this tree mounted read-only. The arguments go to pytest; with
# none, the whole suite:
#
#   indexer/scripts/test.sh [--rebuild] [pytest args]
#   indexer/scripts/test.sh tests/test_fixtures.py -k route-patterns-go
#
#   --rebuild   build the test image again from the current indexer image (also done when it is missing, or was built
#               from another recipe)
#
# Not as the host user: the grammar cache inside the image belongs to root.
set -euo pipefail

indexer="$(cd "$(dirname "$0")/.." && pwd)"
base="${AIDD_INDEXER_IMAGE:-aidd-indexer:local}"
image="${AIDD_INDEXER_TEST_IMAGE:-aidd-indexer-test:local}"

recipe="FROM node:24.21.0-trixie-slim AS node
RUN npm install -g --no-fund --no-audit typescript@6.0.3
FROM $base
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/typescript /opt/typescript
RUN pip install pytest==9.1.1
WORKDIR /src
ENV PYTHONPATH=/src AIDD_TYPESCRIPT=/opt/typescript
ENTRYPOINT []"
stamp=$(printf %s "$recipe" | cksum | cut -d' ' -f1)

rebuild=""
if [ "${1:-}" = "--rebuild" ]; then rebuild=1; shift; fi
built=$(docker image inspect -f '{{ index .Config.Labels "aidd.recipe" }}' "$image" 2>/dev/null || true)
if [ -n "$rebuild" ] || [ "$built" != "$stamp" ]; then
  docker image inspect "$base" >/dev/null 2>&1 \
    || { echo "missing image $base: build the stack's indexer image first (docker compose build at the repo root)" >&2; exit 2; }
  printf '%s\nLABEL aidd.recipe=%s\n' "$recipe" "$stamp" | docker build -q -t "$image" - >/dev/null
fi
[ $# -gt 0 ] || set -- tests
exec docker run --rm -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 -v "$indexer":/src:ro -w /src \
  --entrypoint python "$image" -m pytest -q -p no:cacheprovider "$@"
