#!/usr/bin/env bash
# H6 step 1, the pipeline's own numbers: each run alone, the rounds interleaved across the repos.
#   today: AIDD_PIPELINE=0 (one process, every tree kept until the HTTP pass ends)
#   proto-wN: the map, the reduce and map 2, N workers, no cache
#   fill / warm: 2 workers with a cache, filled by the first run and read by the second on the same tree
#
#   caffeinate -i run_bench.sh ROUNDS REPO...
set -u
here="$(cd "$(dirname "$0")" && pwd)"
res="${AIDD_H6_OUT:-$HOME/.cache/aidd-corpus/h6/step1}"
out="$res/${AIDD_BENCH_OUT:-bench}"
caches="$HOME/.cache/aidd-corpus/h6/cache"
rounds="$1"; shift
mkdir -p "$out"
for run in $(seq 1 "$rounds"); do
  for r in "$@"; do
    src="$HOME/.cache/aidd-corpus/repos/$r"
    [ "$r" != grafana ] || src="$HOME/.cache/aidd-corpus/h6/grafana"
    c="$caches/$r-$run"
    [ ! -d "$c" ] || mv "$c" "$c.old.$$"
    for spec in "today 0 1" "proto-w1 1 1" "proto-w2 1 2" "proto-w4 1 4"; do
      read -r what pipe workers <<<"$spec"
      "$here/bench.sh" "$r-$what-$run" "$src" "$out" "$pipe" "$workers" >>"$out/summary.txt"
    done
    "$here/bench.sh" "$r-fill-$run" "$src" "$out" 1 2 "$c" >>"$out/summary.txt"
    "$here/bench.sh" "$r-warm-$run" "$src" "$out" 1 2 "$c" >>"$out/summary.txt"
    for what in proto-w1 proto-w2 proto-w4 fill warm; do
      echo "  $r-$what-$run vs today: $(python3 "$here/same.py" "$out/$r-today-$run.json.gz" "$out/$r-$what-$run.json.gz")" \
        >>"$out/summary.txt"
    done
  done
done
echo done >>"$out/summary.txt"
