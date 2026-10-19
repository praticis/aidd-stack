#!/usr/bin/env bash
# The micro graph's regression check (scripts/micro.py): full dry-runs of a fixed set of public repositories with a
# base commit of the indexer and with this tree, one container per run, then compared record by record. The base's
# dry-runs are kept per version of the code and reused. Everything runs in the indexer image; the clones and the runs
# live in $AIDD_CORPUS_HOME (default ~/.cache/aidd-corpus), outside the repository.
#
#   indexer/scripts/micro.sh [--base REF] [--base-only] [--jobs N] [--memory SIZE] [--show N] [repo ...]
#
#   --base REF     the commit to compare with (default: main)
#   --base-only    only the base's dry-runs, kept for later runs (CI fills its cache this way)
#   --jobs N       containers at once (default: $AIDD_CORPUS_JOBS, else 2 from 9 GiB of Docker memory, else 1)
#   --memory SIZE  memory cap of each container (default: 5g; grafana's dry-run peaks at 4.4 GiB)
#   --show N       records listed per side of each list that differs (default: 5)
#   repo ...       only these repositories (default: the whole set)
#
# Writes micro/base-<tree>-<image>/ and micro/<label>/ (a <repo>.json.gz and a <repo>.log each) and
# micro/<label>.report.txt, which it also prints: "0 repo(s) differ" when the graph did not change. <tree> is the base's
# `aidd_indexer` tree, so commits with the same code share their base runs; <image> is the image's id, or
# $AIDD_MICRO_IMAGE_KEY where every build gets a new id (CI). Exits 1 when a repository differs, 3 when a dry-run
# failed.
set -euo pipefail

indexer="$(cd "$(dirname "$0")/.." && pwd)"
home="${AIDD_CORPUS_HOME:-$HOME/.cache/aidd-corpus}"
image="${AIDD_INDEXER_IMAGE:-aidd-indexer:local}"
jobs="${AIDD_CORPUS_JOBS:-}"
memory=5g base=main show=5 repos="" base_only=""

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit "$1"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --base) base="$2"; shift 2 ;;
    --base-only) base_only=1; shift ;;
    --jobs) jobs="$2"; shift 2 ;;
    --memory) memory="$2"; shift 2 ;;
    --show) show="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    -*) echo "unknown option: $1" >&2; usage 2 ;;
    *) repos="$repos $1"; shift ;;
  esac
done

# Two at once, the largest beside a smaller one (see the order below), leave room for the stack in a 9 GiB VM.
default_jobs() {
  local vm gib=1073741824
  vm=$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)
  if [ "$vm" -ge $(( 9 * gib )) ]; then echo 2; else echo 1; fi
}
[ -n "$jobs" ] || jobs=$(default_jobs)

docker image inspect "$image" >/dev/null 2>&1 \
  || { echo "missing image $image: build the stack's indexer image first (docker compose build at the repo root)" >&2; exit 2; }
sha=$(git -C "$indexer" rev-parse --verify -q "$base^{commit}") || { echo "unknown --base: $base" >&2; exit 2; }
label="$(date +%F)-$(git -C "$indexer" rev-parse --short HEAD)"
[ -z "$(git -C "$indexer" status --porcelain -- .)" ] || label="$label-dirty"

# The grammars come with the image, so a base run is only reused by the same image.
img="${AIDD_MICRO_IMAGE_KEY:-$(docker image inspect -f '{{.Id}}' "$image" | sed 's/^sha256://' | cut -c1-12)}"
tree=$(git -C "$indexer" rev-parse "$sha:./aidd_indexer")
micro="$home/micro"
base_code="$micro/code-$tree"
base_runs="$micro/base-$tree-$img"
head_runs="$micro/$label"
# the tree may have changed since a run with the same label: only the base's runs are reused
rm -rf "$head_runs"
mkdir -p "$home/repos" "$base_runs" "$head_runs"
if [ ! -d "$base_code" ]; then
  tmp=$(mktemp -d "$micro/.code.XXXXXX")
  git -C "$indexer" archive "$sha" aidd_indexer | tar -x -C "$tmp"
  mv "$tmp" "$base_code"
fi

dock() {
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 \
    -v "$indexer":/src:ro -v "$home":/corpus --label "aidd.micro=$label" "$@"
}

# one dry-run in its own container; prints "<repo> <base|head> <ok|failed(code)> <seconds>s"
dry() {
  local which="$1" code="$2" out="$3" name="$4" t0 status
  t0=$(date +%s)
  if docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/code -e PYTHONDONTWRITEBYTECODE=1 \
      --memory "$memory" --memory-swap "$memory" -v "$code":/code:ro -v "$home/repos/$name":/repo:ro -v "$out":/out \
      --label "aidd.micro=$label" -w /code --entrypoint python "$image" \
      -m aidd_indexer.cli index /repo --tenant micro --dry-run --out "/out/$name.json" >"$out/$name.log" 2>&1; then
    status=ok
    gzip -f "$out/$name.json"
  else
    status="failed($?)"
    rm -f "$out/$name.json"
  fi
  echo "$name $which $status $(( $(date +%s) - t0 ))s"
}
export -f dry
export home image memory label

stop_all() {
  local ids
  ids=$(docker ps -q --filter "label=aidd.micro=$label")
  [ -z "$ids" ] || docker stop $ids >/dev/null
  exit 130
}
trap stop_all INT TERM

# shellcheck disable=SC2086  # the word lists are meant to split
order=$(dock --entrypoint python "$image" /src/scripts/micro.py --dir /corpus/repos --prepare $repos)
echo "micro run $label against $base (${sha:0:10}): $(echo "$order" | wc -w | tr -d ' ') repositories, $jobs at once, $memory each"
# Every base run before any head run: the two dry-runs of the largest repository never share the memory.
{
  for name in $order; do [ -s "$base_runs/$name.json.gz" ] || echo "base $base_code $base_runs $name"; done
  [ -n "$base_only" ] || for name in $order; do echo "head $indexer $head_runs $name"; done
} | xargs -P "$jobs" -L 1 bash -c 'dry "$0" "$1" "$2" "$3"' | tee "$micro/$label.summary.txt"

failed=$(awk '$3 != "ok" {print $1 "(" $2 ")"}' "$micro/$label.summary.txt")
[ -z "$failed" ] || echo "failed (see $micro/<run>/<repo>.log):" $failed >&2
if [ -n "$base_only" ]; then
  echo "base runs in $base_runs"
  [ -z "$failed" ] || exit 3
  exit 0
fi
rc=0
# shellcheck disable=SC2086
dock --entrypoint python "$image" /src/scripts/micro.py --compare "/corpus/micro/base-$tree-$img" "/corpus/micro/$label" \
  --show "$show" $order >"$micro/$label.report.txt" 2>&1 || rc=1
cat "$micro/$label.report.txt"
[ -z "$failed" ] || rc=3
exit "$rc"
