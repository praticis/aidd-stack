#!/usr/bin/env bash
# Which answer explains each CALLS edge of Go repos that changed between two trees of the indexer: what each tree
# types the receivers of method calls as (go_answers.py, once per tree, in the image), then attribution.py over the
# two micro dry-runs. The trees are checkouts, one worktree each, because each answers with its own code.
#
#   indexer/scripts/judgment/go_attribution.sh OLD_TREE NEW_TREE BEFORE AFTER N REPO... [--cases FILE]
#
#   OLD_TREE, NEW_TREE  repository checkouts (their `indexer/` is mounted)
#   BEFORE, AFTER       the micro dry-run directories of those trees (micro.sh leaves them in $C/micro)
#   N                   seeded samples per case and kind
#   --cases FILE        the case table (attribution.py)
#
# The repos are read from $AIDD_CORPUS_HOME/repos (default ~/.cache/aidd-corpus). The answers are kept in
# $AIDD_ATTRIBUTION_OUT (default a new temporary folder, printed first).
set -euo pipefail
[ $# -ge 6 ] || { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

here="$(cd "$(dirname "$0")" && pwd)"
home="${AIDD_CORPUS_HOME:-$HOME/.cache/aidd-corpus}"
image="${AIDD_INDEXER_IMAGE:-aidd-indexer:local}"
out="${AIDD_ATTRIBUTION_OUT:-$(mktemp -d)}"
old="$(cd "$1" && pwd)" new="$(cd "$2" && pwd)" before="$3" after="$4" n="$5"
shift 5
repos=() extra=()
while [ $# -gt 0 ]; do
  case "$1" in
    --*) extra=("$@"); break ;;
    *) repos+=("$1"); shift ;;
  esac
done
mkdir -p "$out"
echo "answers in $out"

answers() {
  docker run --rm -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 -v "$1/indexer":/src:ro -v "$here":/tool:ro \
    -v "$home/repos":/repos:ro --entrypoint python "$image" /tool/go_answers.py /repos "${repos[@]}" > "$2"
}
answers "$old" "$out/old.jsonl"
answers "$new" "$out/new.jsonl"
python3 -I "$here/attribution.py" "$before" "$after" "$out/old.jsonl" "$out/new.jsonl" "$n" "${repos[@]}" \
  --repos "$home/repos" ${extra[@]+"${extra[@]}"}
