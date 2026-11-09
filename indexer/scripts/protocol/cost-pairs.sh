#!/usr/bin/env bash
# The cost of a change in a pass over a repository, main against the branch, in pairs on a quiet machine: corpus.sh --jobs 1
# --no-expected on each tree's own code, the side that goes first flipping from one pair to the next so a drift of the machine
# does not fall on one side; then the change in time and in peak memory per repo (cost_pairs.py). The limit and the reading (the
# median of the first three pairs, say) are written in the plan before the first run.
#   cost-pairs.sh MAIN_TREE BRANCH_TREE [--pairs N] [--prefix NAME] REPO...
#   MAIN_TREE, BRANCH_TREE   checkouts of the repository (each one's indexer/scripts/corpus.sh runs)
#   --pairs N                pairs to run (default 3)
#   --prefix NAME            the runs are NAME-m1, NAME-b1, ... under ~/.cache/aidd-corpus/runs (default cost-<date and time>)
# One heavy job at a time like the corpus: it takes the heavy-job lock, which the corpus.sh it starts then finds held.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
[ $# -ge 3 ] || { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
main_tree="$1" branch_tree="$2"; shift 2
pairs=3 prefix="cost-$(date +%m%d-%H%M%S)" repos=()
while [ $# -gt 0 ]; do
  case "$1" in
    --pairs) pairs="$2"; shift 2 ;;
    --prefix) prefix="$2"; shift 2 ;;
    *) repos+=("$1"); shift ;;
  esac
done
[ ${#repos[@]} -gt 0 ] || { echo "cost-pairs: name at least one repo" >&2; exit 2; }
home="${AIDD_CORPUS_HOME:-$HOME/.cache/aidd-corpus}"
. "$here/../lib/heavy-lock.sh"
heavy_lock "cost-pairs $prefix"
run() {  # run SIDE TREE ROUND
  "$2/indexer/scripts/corpus.sh" --label "$prefix-$1$3" --jobs 1 --no-expected "${repos[@]}" > "$home/$prefix-$1$3.out" 2>&1 \
    || echo "cost-pairs: $prefix-$1$3 ended with an error: see $home/$prefix-$1$3.out" >&2
}
for round in $(seq 1 "$pairs"); do
  if [ $((round % 2)) -eq 1 ]; then first=m second=b; else first=b second=m; fi
  for side in "$first" "$second"; do
    if [ "$side" = m ]; then run m "$main_tree" "$round"; else run b "$branch_tree" "$round"; fi
  done
done
exec python3 -I "$here/cost_pairs.py" "$home" "$prefix" "$pairs"
