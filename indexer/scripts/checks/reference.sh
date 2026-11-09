#!/usr/bin/env bash
# The graph of a tree against its references: the checker's rows for the TS repos that have a floor, then
# judgment/scorecard.py over the tree's micro dry-runs, against checks/reference_floors.txt.
#
#   indexer/scripts/checks/reference.sh [--run DIR] [--floors FILE] [--base-floors FILE] [--out DIR]
#
#   --run DIR           the tree's dry-runs (default: the newest run of micro.sh, $home/micro/<date>-<sha>)
#   --floors FILE       the floors that judge them (default: checks/reference_floors.txt of this tree)
#   --base-floors FILE  the base's floors: the ones this tree lowers are listed (and counted, with --out)
#   --out DIR           also writes reference.txt (what it prints), reference-rc.txt (the scorecard's exit code) and
#                       reference-lowered.txt (the floors this tree lowers, one per line), which `gates.py` reads
#
# The checker's rows depend on the clone and on the checker's code, not on the tree, so they are kept in
# $home/reference/rows by the clone's commit, the checker's code and the test image's recipe, and read back: a pull request
# pays for the checker (about a minute for ghost) only when one of them changed. The checker runs in the test image
# (lib/test-image.sh), one heavy job at a time like the corpus.
#
# Exits as the scorecard does: 0 every number holds, 1 one does not, 2 its input is wrong (and 75 when another heavy job
# holds the lock).
set -euo pipefail

indexer="$(cd "$(dirname "$0")/../.." && pwd)"
home="${AIDD_CORPUS_HOME:-$HOME/.cache/aidd-corpus}"
run="" floors="$indexer/scripts/checks/reference_floors.txt" base_floors="" out=""

usage() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit "$1"; }
while [ $# -gt 0 ]; do
  case "$1" in
    --run) run="$2"; shift 2 ;;
    --floors) floors="$2"; shift 2 ;;
    --base-floors) base_floors="$2"; shift 2 ;;
    --out) out="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "unknown option: $1" >&2; usage 2 ;;
  esac
done

[ -n "$run" ] || run=$(find "$home/micro" -maxdepth 1 -type d -name '[0-9]*' 2>/dev/null | sort | tail -1)
[ -n "$run" ] && [ -d "$run" ] || { echo "no dry-runs of the tree: run micro.sh first, or give --run" >&2; exit 2; }
[ -f "$floors" ] || { echo "no such floors file: $floors" >&2; exit 2; }

. "$indexer/scripts/lib/heavy-lock.sh"
. "$indexer/scripts/lib/test-image.sh"

rows="$home/reference/rows" use="$home/reference/use"
mkdir -p "$rows"
rm -rf "$use" && mkdir -p "$use"
code=$(cat "$indexer"/scripts/checks/ts_*.js | cksum | cut -d' ' -f1)
# the TS repos are the ones with a floor of the precision against the checker
for repo in $(sed -n 's/^\([a-z0-9-]*\)\.typed-precision ::.*/\1/p' "$floors"); do
  clone="$home/repos/$repo"
  [ -d "$clone" ] || { echo "reference: no clone of $repo in $home/repos: its numbers are not measured" >&2; continue; }
  key=$(printf '%s %s %s' "$(git -C "$clone" rev-parse HEAD)" "$code" "$stamp" | cksum | cut -d' ' -f1)
  file="$rows/$repo-$key.jsonl"
  if [ ! -s "$file" ]; then
    heavy_lock "reference $repo"
    test_image_ensure
    docker run --rm -v "$home/repos":/corpus:ro -v "$indexer":/src:ro -e AIDD_TYPESCRIPT=/opt/typescript "$image" \
      node /src/scripts/checks/ts_checker.js --link "/corpus/$repo" > "$file.tmp"
    mv "$file.tmp" "$file"
  fi
  ln -s "$file" "$use/checker-$repo.jsonl"
done

scorecard="$indexer/scripts/judgment/scorecard.py"
report="$(mktemp)" rc=0
python3 -I "$scorecard" "$run" --rows "$use" --floors "$floors" > "$report" || rc=$?
lowered=""
[ -z "$base_floors" ] || lowered=$(python3 -I "$scorecard" --lowered "$base_floors" "$floors")
if [ -n "$lowered" ]; then
  { echo; echo "Floors this change lowers (name, was, is):"; echo; echo "$lowered" | sed 's/^/- /'; } >> "$report"
fi
cat "$report"
if [ -n "$out" ]; then
  mkdir -p "$out"
  cp "$report" "$out/reference.txt"
  echo "$rc" > "$out/reference-rc.txt"
  if [ -n "$lowered" ]; then echo "$lowered" > "$out/reference-lowered.txt"; else : > "$out/reference-lowered.txt"; fi
fi
rm -f "$report"
exit "$rc"
