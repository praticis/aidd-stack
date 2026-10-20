#!/usr/bin/env bash
# H6 step 1, the cache on real pushes: for each push (k-1 → k) of the replay's window, a cold run of k (the
# reference), a cold run of k-1 that fills a cache, a warm run of k on it, and a second warm run of k with no change.
# Each warm run is compared with the cold one, record by record.
#
#   caffeinate -i push_bench.sh REPO K...
set -u
here="$(cd "$(dirname "$0")" && pwd)"
res="${AIDD_H6_OUT:-$HOME/.cache/aidd-corpus/h6/step1}"
repo="$1"; shift
hist="$HOME/.cache/aidd-corpus/h6/replay/$repo-w40.git"
trees="$HOME/.cache/aidd-corpus/h6/replay/trees"
out="$res/push"
mkdir -p "$trees" "$out"
shas=($(git -C "$hist" rev-list --first-parent -n40 replay | tail -r))

tree() {
  local d="$trees/$repo-$1"
  if [ ! -d "$d" ]; then
    mkdir -p "$d.part"
    git -C "$hist" archive "${shas[$1]}" | tar -x -C "$d.part"
    mv "$d.part" "$d"
  fi
  echo "$d"
}

for k in "$@"; do
  a=$(tree $((k - 1))) b=$(tree "$k")
  c="$HOME/.cache/aidd-corpus/h6/cache/push-$repo-$k"
  [ ! -d "$c" ] || mv "$c" "$c.old.$$"
  n=$(git -C "$hist" diff --name-only "${shas[$((k - 1))]}" "${shas[$k]}" | grep -cE '\.(go|cs|py|ts|tsx|js|jsx|mjs|cjs)$')
  echo "$repo push $k: $n parsed file(s) changed" >>"$out/summary.txt"
  "$here/bench.sh" "$repo-$k-cold" "$b" "$out" 1 2 >>"$out/summary.txt"
  "$here/bench.sh" "$repo-$k-fill" "$a" "$out" 1 2 "$c" >>"$out/summary.txt"
  "$here/bench.sh" "$repo-$k-warm" "$b" "$out" 1 2 "$c" >>"$out/summary.txt"
  "$here/bench.sh" "$repo-$k-again" "$b" "$out" 1 2 "$c" >>"$out/summary.txt"
  for w in warm again; do
    echo "  $w vs cold: $(python3 "$here/same.py" "$out/$repo-$k-cold.json.gz" "$out/$repo-$k-$w.json.gz")" >>"$out/summary.txt"
  done
done
