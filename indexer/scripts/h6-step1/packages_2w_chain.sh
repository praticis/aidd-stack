#!/usr/bin/env bash
# H6 step 2, batches by package at 2 workers (the refresher's quota): batches of files and of packages interleaved,
# with a probe of the parent's garbage collection, and with its heap frozen after map 1. Each run is compared with
# today's run of the first bench.
#   caffeinate -i packages_2w_chain.sh
set -u
here="$(cd "$(dirname "$0")" && pwd)"
out="${AIDD_H6_OUT:-$HOME/.cache/aidd-corpus/h6/step1}"
res="$out/packages-2w"
code="$HOME/.cache/aidd-corpus/h6/code/packages-gc-$(date +%H%M%S)"
mkdir -p "$res" "$code" && rsync -a --exclude __pycache__ "$here/../../" "$code/"
python3 "$here/gc_patch.py" "$code"
log="$res/chain.log"
echo "code $code $(date +%T)" >>"$log"
specs() {
  echo "file-w2 file 2"; echo "pkg-w2 package 2"
  [ "$1" = vikunja ] && return
  echo "file-w2-fz file 2 1"; echo "pkg-w2-fz package 2 1"
  [ "$1" = grafana ] || return
  echo "file-w4-fz file 4 1"; echo "pkg-w4-fz package 4 1"
}
for run in 1 2 3; do
  for r in vikunja mattermost grafana; do
    src="$HOME/.cache/aidd-corpus/repos/$r"
    while read -r what batch workers fz; do
      "$here/batch_run.sh" "$code" "$r-$what-$run" "$src" "$res/bench" 1 "$batch" "$workers" "${fz:-}" >>"$res/bench.txt"
      echo "  $r-$what-$run vs today: $(python3 "$here/same.py" "$out/packages/bench/$r-today-1.json.gz" \
        "$res/bench/$r-$what-$run.json.gz")" >>"$res/bench.txt"
    done <<<"$(specs "$r")"
  done
  echo "round $run $(date +%T)" >>"$log"
done
echo "done $(date +%T)" >>"$log"
