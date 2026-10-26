#!/usr/bin/env bash
# The micro graph's check as indexer/scripts/micro.sh runs it, with the tree's dry-runs written to a path no container
# mounted before, then copied, with the base's, to others before they are compared: Docker Desktop breaks the bind mount of a folder
# deleted and made again at one path, and can serve a file it has just written cut short. The base's dry-runs are
# micro.sh's own (run micro.sh --base-only first for a repo it has none of).   micro-fresh.sh LABEL REPO...
set -u
label="$1"; shift
repo="${AIDD_REPO:-$(cd "$(dirname "$0")/../../.." && pwd)}"
indexer=$repo/indexer home=$HOME/.cache/aidd-corpus image=aidd-indexer:local
img=$(docker image inspect -f '{{.Id}}' "$image" | sed 's/^sha256://' | cut -c1-12)
# the base is the commit the branch starts from: main may have moved on with code the dry-runs do not run
tree=$(git -C "$indexer" rev-parse "$(git -C "$indexer" merge-base main HEAD):./aidd_indexer")
base="$home/micro/base-$tree-$img"
stamp=$(date +%H%M%S)
head="$home/micro-fresh/$label-$stamp" copy="$home/micro-fresh/$label-$stamp-copy"
basecopy="$home/micro-fresh/$label-$stamp-base"
mkdir -p "$head"
missing=$(for n in "$@"; do [ -s "$base/$n.json.gz" ] || echo "$n"; done)
[ -z "$missing" ] || { echo "no base run for:" $missing; exit 2; }
dry() {
  local name="$1" t0=$(date +%s)
  if docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/code -e PYTHONDONTWRITEBYTECODE=1 \
      --memory 5g --memory-swap 5g -v "$indexer":/code:ro -v "$home/repos/$name":/repo:ro -v "$head":/out \
      -w /code --entrypoint python "$image" \
      -m aidd_indexer.cli index /repo --tenant micro --dry-run --out "/out/$name.json" >"$head/$name.log" 2>&1; then
    gzip -f "$head/$name.json" && echo "$name head ok $(( $(date +%s) - t0 ))s"
  else
    echo "$name head failed($?) $(( $(date +%s) - t0 ))s"
  fi
}
export -f dry; export indexer home image head
printf '%s\n' "$@" | xargs -P 2 -L 1 bash -c 'dry "$0"' | tee "$head.summary.txt"
failed=$(awk '$3 != "ok" {print $1}' "$head.summary.txt" | tr '\n' ' ')
mkdir -p "$copy" "$basecopy" && rsync -a "$head/" "$copy/" && rsync -a "$base/" "$basecopy/"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$basecopy":/base:ro -v "$copy":/head:ro -v "$indexer":/src:ro --entrypoint python "$image" \
  /src/scripts/micro.py --compare /base /head --show 5 "$@" >"$head.report.txt" 2>&1
rc=$?
cat "$head.report.txt"
if [ -n "$failed" ]; then echo "dry-runs failed (see $head/<repo>.log): $failed"; exit 3; fi
exit "$rc"
