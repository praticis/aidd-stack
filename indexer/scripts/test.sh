#!/usr/bin/env bash
# The indexer's tests in the test image (the indexer image plus pytest), with this tree mounted read-only. The
# arguments go to pytest; with none, the whole suite:
#
#   indexer/scripts/test.sh [--rebuild] [pytest args]
#   indexer/scripts/test.sh tests/test_fixtures.py -k route-patterns-go
#
#   --rebuild   build the test image again from the current indexer image (also done when it is missing)
#
# Not as the host user: the grammar cache inside the image belongs to root.
set -euo pipefail

indexer="$(cd "$(dirname "$0")/.." && pwd)"
base="${AIDD_INDEXER_IMAGE:-aidd-indexer:local}"
image="${AIDD_INDEXER_TEST_IMAGE:-aidd-indexer-test:local}"

rebuild=""
if [ "${1:-}" = "--rebuild" ]; then rebuild=1; shift; fi
if [ -n "$rebuild" ] || ! docker image inspect "$image" >/dev/null 2>&1; then
  docker image inspect "$base" >/dev/null 2>&1 \
    || { echo "missing image $base: build the stack's indexer image first (docker compose build at the repo root)" >&2; exit 2; }
  printf 'FROM %s\nRUN pip install pytest==9.1.1\nWORKDIR /src\nENV PYTHONPATH=/src\nENTRYPOINT []\n' "$base" \
    | docker build -q -t "$image" - >/dev/null
fi
[ $# -gt 0 ] || set -- tests
exec docker run --rm -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 -v "$indexer":/src:ro -w /src \
  --entrypoint python "$image" -m pytest -q -p no:cacheprovider "$@"
