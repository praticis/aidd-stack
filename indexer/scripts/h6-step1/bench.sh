#!/usr/bin/env bash
# H6 step 1: one full dry-run of a tree in its own container, under one memory cap; prints its wall time and the
# cgroup's peak memory. The code is the prototype's worktree; AIDD_PIPELINE=0 runs today's extraction.
#
#   bench.sh LABEL SRC_DIR OUT_DIR PIPELINE WORKERS [CACHE_DIR]
set -u
code="${AIDD_H6_CODE:-$(cd "$(dirname "$0")/../.." && pwd)}"
label="$1" src="$2" out="$3" pipe="$4" workers="$5" cache="${6:-}"
mkdir -p "$out"
extra=()
[ -z "$cache" ] || { mkdir -p "$cache"; extra=(-v "$cache":/cache -e AIDD_CACHE=/cache); }
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/code -e PYTHONDONTWRITEBYTECODE=1 \
  --memory 8g --memory-swap 8g -e AIDD_PIPELINE="$pipe" -e AIDD_WORKERS="$workers" ${extra[@]+"${extra[@]}"} \
  -v "$code":/code:ro -v "$src":/repo:ro -v "$out":/out -w /code --entrypoint sh aidd-indexer:local -c '
    python -c "
import subprocess, sys, time
t = time.perf_counter()
rc = subprocess.call([sys.executable, \"-m\", \"aidd_indexer.cli\", \"index\", \"/repo\", \"--tenant\", \"micro\",
                      \"--dry-run\", \"--out\", \"/out/$0.json\"])
print(f\"wall={time.perf_counter() - t:.2f}\")
sys.exit(rc)"
    rc=$?; echo "peak=$(cat /sys/fs/cgroup/memory.peak)"; exit $rc' "$label" >"$out/$label.log" 2>&1
rc=$?
[ ! -f "$out/$label.json" ] || gzip -f "$out/$label.json"
echo "$label rc=$rc $(grep -o 'wall=[0-9.]*' "$out/$label.log") $(grep -o 'peak=[0-9]*' "$out/$label.log") $(grep -o '\[pipeline\].*' "$out/$label.log")"
