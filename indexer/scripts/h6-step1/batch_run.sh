#!/usr/bin/env bash
# One full dry-run of SRC with the code at CODE, in its own container: wall time, the cgroup's peak memory, the
# pipeline's counters and, when the code has the probe, the parent's garbage collection.
#   batch_run.sh CODE LABEL SRC OUT PIPELINE BATCH WORKERS [FREEZE]
set -u
code="$1" label="$2" src="$3" out="$4" pipe="$5" batch="$6" workers="$7" fz="${8:-}"
mkdir -p "$out"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/code -e PYTHONDONTWRITEBYTECODE=1 \
  --memory 8g --memory-swap 8g -e AIDD_PIPELINE="$pipe" -e AIDD_BATCH="$batch" -e AIDD_WORKERS="$workers" \
  -e AIDD_GCPROBE=1 -e AIDD_GCFREEZE="$fz" \
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
echo "$label rc=$rc $(grep -o 'wall=[0-9.]*' "$out/$label.log") $(grep -o 'peak=[0-9]*' "$out/$label.log")" \
  "$(grep -o '\[pipeline\].*' "$out/$label.log") $(grep -o '\[gc\].*' "$out/$label.log")"
