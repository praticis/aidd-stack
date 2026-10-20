#!/usr/bin/env bash
# H6 step 1, second pass on the final prototype: tests, the micro set, the bench (3 rounds), the warm pushes.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
res="${AIDD_H6_OUT:-$HOME/.cache/aidd-corpus/h6/step1}"
code="$(cd "$here/../.." && pwd)"
mkdir -p "$res"
log="$res/chain2.log"
echo "tests $(date +%T)" >>"$log"
"$code/scripts/test.sh" >"$res/tests-3.txt" 2>&1; echo "tests rc=$? $(tail -1 "$res/tests-3.txt") $(date +%T)" >>"$log"
"$code/scripts/micro.sh" --base main >"$res/micro-2.txt" 2>&1; echo "micro rc=$? $(date +%T)" >>"$log"
AIDD_BENCH_OUT=bench2 "$here/run_bench.sh" 3 vikunja mattermost grafana; echo "bench rc=$? $(date +%T)" >>"$log"
"$here/push_bench.sh" vikunja 12 28 38; echo "push vikunja rc=$? $(date +%T)" >>"$log"
"$here/push_bench.sh" mattermost 19 25 30; echo "push mattermost rc=$? $(date +%T)" >>"$log"
echo done >>"$log"
