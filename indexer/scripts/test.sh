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
. "$indexer/scripts/lib/test-image.sh"

rebuild=""
if [ "${1:-}" = "--rebuild" ]; then rebuild=1; shift; fi
# the whole suite is a heavy job, the image build too; a file, a test or a folder under tests/ is not
narrow=""
for arg in "$@"; do
  case "$arg" in *.py | *::* | tests/*) narrow=1 ;; esac
done
if [ -z "$narrow" ]; then
  . "$indexer/scripts/lib/heavy-lock.sh"
  heavy_lock test-suite
fi
if [ -n "$rebuild" ]; then test_image_ensure --rebuild; else test_image_ensure; fi
[ $# -gt 0 ] || set -- tests
exec docker run --rm -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 -v "$indexer":/src:ro -w /src \
  --entrypoint python "$image" -m pytest -q -p no:cacheprovider "$@"
