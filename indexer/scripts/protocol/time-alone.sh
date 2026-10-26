#!/usr/bin/env bash
# A change timed alone, main then the branch: the corpus's wall time, then one dry-run at a time of the largest
# C# repos (or $AIDD_TIME_REPOS), with the resolver's own time from each log.
#   time-alone.sh MAIN_WORKTREE BRANCH_WORKTREE
set -u
home=$HOME/.cache/aidd-corpus
for side in "$1" "$2"; do
  name=$(basename "$side")
  (cd "$side" && indexer/scripts/corpus.sh --label "$(date +%F-%H%M%S)-time-$name" --baseline "${AIDD_BASELINE:-2026-10-18-v2-baseline-29}" 2>&1 \
    | grep -E "repo\(s\) differ|wall")
done
for repo in ${AIDD_TIME_REPOS:-umbraco elsa bitwarden smartstore}; do
  for side in "$1" "$2"; do
    out=$(mktemp -d "$home/micro-fresh/time-XXXXXX")
    t0=$(date +%s)
    docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/code -e PYTHONDONTWRITEBYTECODE=1 \
      --memory 5g --memory-swap 5g -v "$side/indexer":/code:ro -v "$home/repos/$repo":/repo:ro -v "$out":/out \
      -w /code --entrypoint python aidd-indexer:local -m aidd_indexer.cli index /repo --tenant micro --dry-run \
      --out /out/x.json >"$out/log" 2>&1
    echo "$repo $(basename "$side"): $(( $(date +%s) - t0 ))s total; $(grep -oE '\[resolve\].*' "$out/log" | tail -1)"
    rm -rf "$out"
  done
done
