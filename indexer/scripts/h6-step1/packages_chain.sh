#!/usr/bin/env bash
# H6 step 2, batches by package: the corpus, the micro set against main's runs, then the bench (3 rounds) of today,
# batches of files and batches of packages. Docker Desktop can serve a stale copy of a mounted tree, so the code is
# copied to a fresh path, with batches of packages as the default.
#   caffeinate -i packages_chain.sh MICRO_BASE   (MICRO_BASE: the directory of main's micro dry-runs)
set -u
here="$(cd "$(dirname "$0")" && pwd)"
res="${AIDD_H6_OUT:-$HOME/.cache/aidd-corpus/h6/step1}/packages"
base="$1"
code="$HOME/.cache/aidd-corpus/h6/code/packages-$(date +%H%M%S)"
mkdir -p "$res" "$code" && rsync -a --exclude __pycache__ "$here/../../" "$code/"
sed -i '' 's/os.getenv("AIDD_BATCH", "file") == "package"/os.getenv("AIDD_BATCH", "package") == "package"/' \
  "$code/aidd_indexer/core/pipeline.py"
log="$res/chain.log"
echo "code $code $(date +%T)" >>"$log"
"$code/scripts/test.sh" >"$res/tests.txt" 2>&1; echo "tests rc=$? $(tail -1 "$res/tests.txt") $(date +%T)" >>"$log"
"$code/scripts/corpus.sh" --label 2026-10-20-h6-r3 --baseline 2026-10-18-v2-baseline-28 --memory 4g \
  >"$res/corpus.txt" 2>&1; echo "corpus rc=$? $(grep 'repo(s) differ' "$res/corpus.txt") $(date +%T)" >>"$log"
for r in grafana umbraco mattermost ghost gitea outline jellyfin vikunja netbox btcpayserver dispatch eshop; do
  "$here/batch_run.sh" "$code" "$r" "$HOME/.cache/aidd-corpus/repos/$r" "$res/micro" 1 package 2 >>"$res/micro.txt"
  echo "  $r vs main: $(python3 "$here/same.py" "$base/$r.json.gz" "$res/micro/$r.json.gz")" >>"$res/micro.txt"
done
echo "micro done $(grep -c ': same' "$res/micro.txt") same $(date +%T)" >>"$log"
for run in 1 2 3; do
  for r in vikunja mattermost grafana; do
    src="$HOME/.cache/aidd-corpus/repos/$r"
    for spec in "today 0 file 1" "file-w1 1 file 1" "file-w4 1 file 4" "pkg-w1 1 package 1" "pkg-w2 1 package 2" \
                "pkg-w4 1 package 4"; do
      read -r what pipe batch workers <<<"$spec"
      "$here/batch_run.sh" "$code" "$r-$what-$run" "$src" "$res/bench" "$pipe" "$batch" "$workers" >>"$res/bench.txt"
    done
    for what in file-w1 file-w4 pkg-w1 pkg-w2 pkg-w4; do
      echo "  $r-$what-$run vs today: $(python3 "$here/same.py" "$res/bench/$r-today-$run.json.gz" \
        "$res/bench/$r-$what-$run.json.gz")" >>"$res/bench.txt"
    done
  done
done
echo "done $(date +%T)" >>"$log"
