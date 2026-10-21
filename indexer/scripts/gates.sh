#!/usr/bin/env bash
# The method's gates (scripts/gates.py) in the indexer image, over corpus runs under $AIDD_CORPUS_HOME (default
# ~/.cache/aidd-corpus): the same check CI runs on a pull request, for anyone to run before pushing.
#
#   indexer/scripts/gates.sh --base runs/<base> --head runs/<branch>
#                            [--holdout-base runs/<base>-holdout --holdout-head runs/<branch>-holdout]
#                            [--label refactor] [--label holdout-measurement]
#                            [--branch=NAME] [--commits -] [--micro-rc N]
#
# The runs come from `corpus.sh --label`. Whether the branch is a refactor, as CI decides it:
#   git log --format=%s origin/main..HEAD | indexer/scripts/gates.sh ... --branch="$(git branch --show-current)" --commits -
# Prints the report in Markdown; exits 1 when a gate fails.
set -euo pipefail

indexer="$(cd "$(dirname "$0")/.." && pwd)"
home="${AIDD_CORPUS_HOME:-$HOME/.cache/aidd-corpus}"
image="${AIDD_INDEXER_IMAGE:-aidd-indexer:local}"

args=()
for a in "$@"; do
  case "$a" in
    runs/*) args+=("/corpus/$a") ;;
    *) args+=("$a") ;;
  esac
done
exec docker run --rm -i --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$indexer":/src:ro -v "$home":/corpus:ro --entrypoint python "$image" /src/scripts/gates.py "${args[@]}"
