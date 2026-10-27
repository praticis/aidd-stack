#!/usr/bin/env bash
# The shape ratchet on the working tree against REF, in the indexer's image; extra args go to ruff's C901 listing
# of the given paths instead (REF defaults to origin/main).   shape.sh [REF] | shape.sh --c901 PATH...
repo="$(cd "$(dirname "$0")/../../.." && pwd)"
setup="git config --global --add safe.directory /repo && pip install -q --root-user-action=ignore ruff==0.17.1 >/dev/null 2>&1"
if [ "${1:-}" = "--c901" ]; then
  shift
  cmd="$setup && ruff check --no-cache --isolated --select C901 --output-format concise --config 'lint.mccabe.max-complexity=0' $* | grep -v '^Found'"
else
  cmd="$setup && python indexer/scripts/shape.py --against '${1:-origin/main}'"
fi
docker run --rm -e HOME=/tmp -v "$repo":/repo:ro -w /repo --entrypoint bash aidd-indexer:local -c "$cmd"
