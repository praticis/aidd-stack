#!/usr/bin/env bash
# The public HTTP corpus (scripts/http_corpus.py) in parallel: one container per repository, the largest first, each
# under a memory cap; then one report for the whole run, with the diff against a baseline and precision/recall against
# the gabaritos. Everything runs in the indexer image with this tree mounted read-only; the clones and the runs live
# in $AIDD_CORPUS_HOME (default ~/.cache/aidd-corpus), outside the repository.
#
#   indexer/scripts/corpus.sh [--label NAME] [--baseline NAME] [--holdout] [--jobs N] [--memory SIZE] [--show N]
#                             [--no-expected] [repo ...]
#
#   --label NAME     the run's directory under runs/ (default: <date>-<commit>, plus -dirty with local changes)
#   --baseline NAME  an earlier run under runs/ to diff against
#   --holdout        the hold-out set instead of the corpus, with its own gabaritos
#   --jobs N         containers at once (default: $AIDD_CORPUS_JOBS, else by Docker's memory: 3 from 9 GiB, 2 from
#                    7 GiB, else 1)
#   --memory SIZE    memory cap of each container (default: $AIDD_CORPUS_MEMORY, else 3g)
#   --show N         items listed per repository in the report (default: 60)
#   --no-expected    no precision/recall against the gabaritos
#   repo ...         only these repositories (default: every pinned one)
#
# Writes runs/<label>/<repo>.json, and in runs/<label>.logs/ each container's log (with its peak memory), summary.txt
# and report.txt, which it also prints. Exits 1 when a repository failed, over the memory cap for instance: the report
# leaves it out and the summary names it.
set -euo pipefail

indexer="$(cd "$(dirname "$0")/.." && pwd)"
home="${AIDD_CORPUS_HOME:-$HOME/.cache/aidd-corpus}"
image="${AIDD_INDEXER_IMAGE:-aidd-indexer:local}"
jobs="${AIDD_CORPUS_JOBS:-}"
memory="${AIDD_CORPUS_MEMORY:-3g}"
label="" baseline="" holdout="" show=60 expected="--expected" repos=""

usage() { sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit "$1"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --label) label="$2"; shift 2 ;;
    --baseline) baseline="$2"; shift 2 ;;
    --holdout) holdout="--holdout"; shift ;;
    --jobs) jobs="$2"; shift 2 ;;
    --memory) memory="$2"; shift 2 ;;
    --show) show="$2"; shift 2 ;;
    --no-expected) expected=""; shift ;;
    -h|--help) usage 0 ;;
    -*) echo "unknown option: $1" >&2; usage 2 ;;
    *) repos="$repos $1"; shift ;;
  esac
done

# The three largest repositories peak at about 5.5 GB together and the stack's own containers hold about 3 GB: past
# the VM's memory, its OOM killer may pick one of those instead of a corpus container.
default_jobs() {
  local vm gib=1073741824
  vm=$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)
  if [ "$vm" -ge $(( 9 * gib )) ]; then echo 3; elif [ "$vm" -ge $(( 7 * gib )) ]; then echo 2; else echo 1; fi
}
[ -n "$jobs" ] || jobs=$(default_jobs)

if [ -z "$label" ]; then
  label="$(date +%F)-$(git -C "$indexer" rev-parse --short HEAD)"
  [ -z "$(git -C "$indexer" status --porcelain -- .)" ] || label="$label-dirty"
  [ -z "$holdout" ] || label="$label-holdout"
fi
docker image inspect "$image" >/dev/null 2>&1 \
  || { echo "missing image $image: build the stack's indexer image first (docker compose build at the repo root)" >&2; exit 2; }
[ -z "$baseline" ] || [ -d "$home/runs/$baseline" ] || { echo "no baseline run: $home/runs/$baseline" >&2; exit 2; }
run_dir="$home/runs/$label"
log_dir="$home/runs/$label.logs"
[ ! -e "$run_dir" ] || { echo "the run $label exists already: pick another --label" >&2; exit 2; }
mkdir -p "$home/repos" "$run_dir" "$log_dir"

dock() {
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 \
    -v "$indexer":/src:ro -v "$home":/corpus --label "aidd.corpus=$label" "$@"
}

# one repository in its own container; prints "<repo> <ok|failed(code)> <seconds>s <peak bytes>"
one() {
  local name="$1" t0 status
  t0=$(date +%s)
  if docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/src -e PYTHONDONTWRITEBYTECODE=1 \
      -v "$indexer":/src:ro -v "$home":/corpus --label "aidd.corpus=$label" \
      --memory "$memory" --memory-swap "$memory" --entrypoint sh "$image" -c \
      'python /src/scripts/http_corpus.py --dir /corpus/repos $0 --json "/corpus/runs/$1" "$2"; rc=$?
       echo "peak_memory_bytes=$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo 0)"; exit $rc' \
      "$holdout" "$label" "$name" >"$log_dir/$name.log" 2>&1; then
    status=ok
  else
    status="failed($?)"
  fi
  echo "$name $status $(( $(date +%s) - t0 ))s $(sed -n 's/^peak_memory_bytes=//p' "$log_dir/$name.log" | tail -1)"
}
export -f one
export indexer home image memory label log_dir holdout

stop_all() {
  local ids
  ids=$(docker ps -q --filter "label=aidd.corpus=$label")
  [ -z "$ids" ] || docker stop $ids >/dev/null
  exit 130
}
trap stop_all INT TERM

# shellcheck disable=SC2086  # the word lists are meant to split
order=$(dock --entrypoint python "$image" /src/scripts/http_corpus.py --dir /corpus/repos $holdout --list $repos)
count=$(echo "$order" | wc -w | tr -d ' ')
echo "corpus run $label: $count repositories, $jobs at once, $memory each"
t0=$(date +%s)
echo "$order" | xargs -P "$jobs" -I{} bash -c 'one "$1"' _ {} | tee "$log_dir/summary.txt"
wall=$(( $(date +%s) - t0 ))

ok=$(awk '$2 == "ok" {print $1}' "$log_dir/summary.txt")
failed=$(awk '$2 != "ok" {print $1}' "$log_dir/summary.txt")
if [ -n "$ok" ]; then
  # shellcheck disable=SC2086
  dock --entrypoint python "$image" /src/scripts/http_corpus.py --dir /corpus/repos $holdout \
    --reuse "/corpus/runs/$label" ${baseline:+--baseline "/corpus/runs/$baseline"} $expected --show "$show" $ok \
    >"$log_dir/report.txt" 2>&1
  cat "$log_dir/report.txt"
fi
echo
echo "run $label: ${wall}s wall, $jobs at once under $memory each; report in $log_dir/report.txt"
echo "largest peaks:" $(sort -k4 -nr "$log_dir/summary.txt" | head -3 | awk '{ printf "%s %.0f MiB (%s)  ", $1, $4 / 1048576, $3 }')
if [ -n "$failed" ]; then
  echo "failed (see $log_dir/<repo>.log):" $failed >&2
  exit 1
fi
