#!/usr/bin/env bash
# The graph of a tree against its references: the checker's rows for the TS repos of the micro set, the scope index's agreement
# with CPython's symbol table on its Python repos, then judgment/scorecard.py over the tree's micro dry-runs, and the base's,
# against checks/reference_floors.txt.
#
#   indexer/scripts/checks/reference.sh [--run DIR] [--base DIR] [--floors FILE] [--base-floors FILE] [--out DIR] [--rows-only]
#
#   --run DIR           the tree's dry-runs (default: the newest run of micro.sh, $home/micro/<date>-<sha>)
#   --base DIR          the base's dry-runs ($home/micro/base-...): the wins the tree loses and the numbers' change are read from them
#   --floors FILE       the bounds that judge the tree (default: checks/reference_floors.txt of this tree)
#   --base-floors FILE  the base's bounds: the ones this tree lowers, or deletes, are listed (and counted, with --out)
#   --out DIR           also writes reference.txt (what it prints), reference-rc.txt (the scorecard's exit code) and
#                       reference-lowered.txt (the bounds this tree lowers, one per line), which `gates.py` reads, and
#                       measured.txt (the counts it measured, as lines of bounds), which `floors_bot.py` reads
#   --rows-only         only make the checker's rows, so that a pull request finds them (what a push to main does)
#
# The TS repos are the ones the micro set (`micro.py --references`) says TypeScript's checker is the reference of: a repo is
# not left out because its bounds are gone. The checker's rows depend on the clone and on the checker's code, not on the tree,
# so they are kept in $home/reference/rows by the clone's commit, the checker's code and the test image's recipe, and read back:
# a pull request pays for the checker (about a minute for ghost) only when one of them changed. The checker runs in the test
# image (lib/test-image.sh), one heavy job at a time like the corpus. A clone that is missing is cloned at its pin.
#
# The Python repos are the ones `micro.py --symtable` names. The scope index is the tree's own code, so its comparison with
# `symtable` (checks/python_scopes.py, in the indexer image, a few seconds) is made on each run and kept nowhere.
#
# Exits as the scorecard does: 0 every count holds, 1 one does not, 3 only wins are lost, 2 its input is wrong; 75 when another
# heavy job holds the lock. Any other status is a run that did not finish (a missing clone, the image, the checker), and the
# caller must not take it for a result.
set -euo pipefail

indexer="$(cd "$(dirname "$0")/../.." && pwd)"
home="${AIDD_CORPUS_HOME:-$HOME/.cache/aidd-corpus}"
run="" base_run="" floors="$indexer/scripts/checks/reference_floors.txt" base_floors="" out="" rows_only=""

usage() { sed -n '2,/^set -/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit "$1"; }
while [ $# -gt 0 ]; do
  case "$1" in
    --run) run="$2"; shift 2 ;;
    --base) base_run="$2"; shift 2 ;;
    --floors) floors="$2"; shift 2 ;;
    --base-floors) base_floors="$2"; shift 2 ;;
    --out) out="$2"; shift 2 ;;
    --rows-only) rows_only=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "unknown option: $1" >&2; usage 2 ;;
  esac
done

if [ -z "$rows_only" ]; then
  [ -n "$run" ] || run=$(find "$home/micro" -maxdepth 1 -type d -name '[0-9]*' 2>/dev/null | sort | tail -1)
  [ -n "$run" ] && [ -d "$run" ] || { echo "no dry-runs of the tree: run micro.sh first, or give --run" >&2; exit 2; }
  [ -f "$floors" ] || { echo "no such floors file: $floors" >&2; exit 2; }
  [ -z "$base_run" ] || [ -d "$base_run" ] || { echo "no such directory of dry-runs: $base_run" >&2; exit 2; }
fi

. "$indexer/scripts/lib/heavy-lock.sh"
. "$indexer/scripts/lib/test-image.sh"

micro() { docker run --rm -e PYTHONPATH=/src -v "$indexer":/src:ro "$@"; }
repos=$(micro --entrypoint python "$base" /src/scripts/micro.py --references)
[ -n "$repos" ] || { echo "reference: the micro set names no repo TypeScript's checker is the reference of" >&2; exit 2; }
python_repos=$(micro --entrypoint python "$base" /src/scripts/micro.py --symtable)
[ -n "$python_repos" ] || { echo "reference: the micro set names no repo CPython's symbol table is the reference of" >&2; exit 2; }

rows="$home/reference/rows" use="$home/reference/use"
mkdir -p "$rows" "$home/repos"
rm -rf "$use" && mkdir -p "$use"
code=$(cat "$indexer"/scripts/checks/ts_*.js | cksum | cut -d' ' -f1)

# the clone of a repo, made at its pin when it is missing
ensure_clone() {
  local clone="$home/repos/$1"
  if [ ! -d "$clone" ]; then
    micro -v "$home/repos":/corpus/repos --entrypoint python "$base" /src/scripts/micro.py --dir /corpus/repos --prepare "$1" >/dev/null
  fi
  [ -d "$clone" ] || { echo "reference: no clone of $1 in $home/repos, and it could not be made" >&2; exit 2; }
}

for repo in $repos; do
  ensure_clone "$repo"
  clone="$home/repos/$repo"
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
[ -z "$rows_only" ] || exit 0

for repo in $python_repos; do ensure_clone "$repo"; done
# a few seconds and little memory, so it takes no lock; its samples of what differs go to the log
micro -v "$home/repos":/corpus:ro -v "$use":/out --entrypoint python "$base" /src/scripts/checks/python_scopes.py \
  --repos $python_repos --json /out/scopes.json > "$use/scopes.txt"
cat "$use/scopes.txt" >&2

scorecard="$indexer/scripts/judgment/scorecard.py"
report="$(mktemp)" rc=0
args=("$run" --rows "$use" --scopes "$use/scopes.json" --floors "$floors")
[ -z "$base_run" ] || args+=(--base "$base_run")
[ -z "$out" ] || { mkdir -p "$out"; args+=(--measured "$out/measured.txt"); }
python3 -I "$scorecard" "${args[@]}" > "$report" || rc=$?
lowered=""
[ -z "$base_floors" ] || lowered=$(python3 -I "$scorecard" --lowered "$base_floors" "$floors")
if [ -n "$lowered" ]; then
  { echo; echo "Bounds this change lowers:"; echo; echo "$lowered" | sed 's/^/- /'; } >> "$report"
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
