#!/usr/bin/env bash
# H6 step 1, one thing at a time: the HTTP corpus against baseline-28, the replay of vikunja and mattermost, then the
# pipeline's bench (3 rounds of vikunja and mattermost, 1 of grafana).
set -u
here="$(cd "$(dirname "$0")" && pwd)"
res="${AIDD_H6_OUT:-$HOME/.cache/aidd-corpus/h6/step1}"
code="$(cd "$here/../.." && pwd)"
mkdir -p "$res"
log="$res/chain.log"
echo "corpus $(date +%T)" >>"$log"
"$code/scripts/corpus.sh" --label 2026-10-20-h6-proto --baseline 2026-10-18-v2-baseline-28 --memory 4g \
  >"$res/corpus-1.txt" 2>&1; echo "corpus rc=$? $(date +%T)" >>"$log"
mkdir -p "$res/replay"
for r in vikunja mattermost; do
  echo "replay $r $(date +%T)" >>"$log"
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/code -e PYTHONDONTWRITEBYTECODE=1 \
    --memory 8g --memory-swap 8g -v "$code":/code:ro -v "$here":/step1:ro \
    -v "$HOME/.cache/aidd-corpus/h6/replay/$r-w40.git":/hist:ro -v "$res/replay":/out \
    -w /code --entrypoint python aidd-indexer:local /step1/replay.py /hist --name "$r" --out "/out/$r" \
    --commits 40 --workers 4 >"$res/replay-$r.txt" 2>&1
  echo "replay $r rc=$? $(date +%T)" >>"$log"
done
echo "bench $(date +%T)" >>"$log"
"$here/run_bench.sh" 3 vikunja mattermost; echo "bench rc=$? $(date +%T)" >>"$log"
"$here/run_bench.sh" 1 grafana; echo "bench grafana rc=$? $(date +%T)" >>"$log"
echo done >>"$log"
