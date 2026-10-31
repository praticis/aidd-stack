#!/usr/bin/env bash
# The live validation of a PR (docs/indexer/method.md §4.7 and §4.8), one command per step. It reads the live install and
# never changes it; what it writes goes to $AIDD_LIVE (default .local/indexer/live, private, outside git), in inflight/.
#   validate.sh before BEFORE_COMMIT AFTER_COMMIT   before the reinstall: both codes, the picture, the golden answers, the
#                                                   dry-runs of every snapshot, compared
#   validate.sh after                               after the author's reinstall: the same picture and answers, and the
#                                                   graph against the dry-runs
#   validate.sh rotate --yes                        the PR is validated: inflight/ becomes merged/, the old merged/ goes
# BEFORE_COMMIT is main before the merge and AFTER_COMMIT the merge. `before` refuses when the installed code is not
# BEFORE_COMMIT's, or when inflight/ exists: the "before" is taken once and never rewritten. `after` refuses until the
# installed code is AFTER_COMMIT's and, when the code that shapes the graph changed, every snapshot's last run since the
# before is ok and every snapshot holds a build other than the before's: a refresh before the reinstall ran the old code
# (the refresh runs every 15 min). When it did not change, the build cannot tell the codes apart and the refresh
# re-indexes nothing, so `after` refuses only a last run since the before that is not ok, or a build that moved. A
# refusal writes no picture, so `after` runs again.
# It prints counts only; the judgment of the numbers is the author's or the agent's.
set -euo pipefail

repo="$(cd "$(dirname "$0")/../../.." && pwd)"
V="$repo/indexer/scripts/live"
live="${AIDD_LIVE:-$repo/.local/indexer/live}"
home="${AIDD_HOME:-$HOME/.aidd}"
calls="$live/golden-calls.json"
inflight="$live/inflight"
summary() { python3 -I "$V/validate_summary.py" "$@"; }
die() { echo "validate: $*" >&2; exit 2; }

# DEST holds what SUBTREE holds in COMMIT, file by file, and nothing else (bytecode caches aside)
same_tree() {  # same_tree COMMIT SUBTREE DEST
  local commit="$1" subtree="$2" dest="$3" n=0 bad=0 meta path
  while IFS=$'\t' read -r meta path; do
    set -- $meta
    n=$((n + 1))
    [ "$(git -C "$repo" hash-object "$dest/${path#"$subtree"/}" 2>/dev/null)" = "$3" ] || bad=$((bad + 1))
  done < <(git -C "$repo" ls-tree -r "$commit" "$subtree")
  local extra
  extra=$(find "$dest" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' | wc -l | tr -d ' ')
  [ "$bad" = 0 ] && [ "$extra" = "$n" ]
}

# a copy a container sees has as many files as the host's: a folder recreated at one path gets served stale
seen_by_docker() {  # seen_by_docker DIR
  local host in_container
  host=$(find "$1/aidd_indexer" -type f | wc -l | tr -d ' ')
  in_container=$(docker run --rm -v "$1":/code:ro --entrypoint sh aidd-indexer:local -c 'find /code/aidd_indexer -type f | wc -l' | tr -d ' ')
  [ "$host" = "$in_container" ]
}

commit_of() { git -C "$repo" rev-parse --verify -q "$1^{commit}" || die "$1 is not a commit"; }

runs_since() {  # runs_since ISO_TIME: the index runs after it, one row each
  docker exec -i aidd-core-neo4j sh -c 'cypher-shell -u neo4j -p "${NEO4J_AUTH#*/}" --format plain' <<<"MATCH (r:IndexRun) \
    WHERE r.started_at > datetime('$1') RETURN r.tenant AS tenant, r.repo AS repo, r.ref AS ref, r.status AS status, \
    size(r.errors) AS n_errors, r.commit_sha AS sha, r.started_at AS started ORDER BY tenant, repo, ref, started;"
}

builds() {  # each snapshot's build in the graph, one row each
  docker exec -i aidd-core-neo4j sh -c 'cypher-shell -u neo4j -p "${NEO4J_AUTH#*/}" --format plain' <<<"MATCH (s:Snapshot) \
    RETURN s.tenant AS tenant, s.repo AS repo, s.ref AS ref, s.indexer_build AS build ORDER BY tenant, repo, ref;"
}

# the parts of the code the build fingerprints (core/build.py): when none changed, the build cannot tell the codes apart
shapes_changed() {  # shapes_changed OLD NEW
  ! git -C "$repo" diff --quiet "$1" "$2" -- indexer/aidd_indexer/__init__.py indexer/aidd_indexer/cli.py \
    indexer/aidd_indexer/core indexer/aidd_indexer/languages indexer/aidd_indexer/conventions indexer/conventions
}

recorded() { sed -n "s/^$1 //p" "$inflight/commits.txt"; }

before() {
  local old new
  old=$(commit_of "${1:?usage: validate.sh before BEFORE_COMMIT AFTER_COMMIT}")
  new=$(commit_of "${2:?usage: validate.sh before BEFORE_COMMIT AFTER_COMMIT}")
  [ ! -e "$inflight" ] || die "$inflight exists: the before is taken once. If that PR is validated, run 'validate.sh rotate --yes'"
  (cd "$live" && shasum -a 256 -c SHA256SUMS >/dev/null) || die "the golden calls file does not match $live/SHA256SUMS"
  same_tree "$old" indexer/aidd_indexer "$home/indexer/aidd_indexer" \
    || die "the installed code is not ${old:0:7}'s: the before can only be taken before the reinstall"
  mkdir -p "$inflight/main_src" "$inflight/head_src"
  # only the package a dry-run imports: an IDE watching the folder builds a test fixture's project in place
  git -C "$repo" archive "$old" indexer/aidd_indexer | tar -x -C "$inflight/main_src"
  git -C "$repo" archive "$new" indexer/aidd_indexer | tar -x -C "$inflight/head_src"
  same_tree "$old" indexer/aidd_indexer "$inflight/main_src/indexer/aidd_indexer" \
    || die "the copy of ${old:0:7} does not match git"
  same_tree "$new" indexer/aidd_indexer "$inflight/head_src/indexer/aidd_indexer" \
    || die "the copy of ${new:0:7} does not match git"
  seen_by_docker "$inflight/main_src/indexer" && seen_by_docker "$inflight/head_src/indexer" \
    || die "a container sees other files than the host's in $inflight: use a fresh path"
  printf 'before_commit %s\nafter_commit %s\ntools_commit %s\n' "$old" "$new" "$(git -C "$repo" rev-parse HEAD)" \
    > "$inflight/commits.txt"
  "$V/pre-merge.sh" "$inflight" "$calls" | tee "$inflight/pre-merge.log"
  ! grep -qv ' rc=0$' "$inflight/pre-merge.log" || die "a step failed: see $inflight/pre-merge.log and the files beside it"
  echo "before_done_at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$inflight/commits.txt"
  (cd "$inflight" && { find before dry -type f | sort | xargs shasum -a 256; shasum -a 256 ./*.txt pre-merge.log; } > SHA256SUMS)
  echo "sealed: $inflight/SHA256SUMS ($(wc -l < "$inflight/SHA256SUMS" | tr -d ' ') files). Now the author reinstalls from main."
  summary before "$inflight"
}

after() {
  [ -d "$inflight/before" ] || die "no before in $inflight: it is taken with 'validate.sh before', before the reinstall"
  [ ! -e "$inflight/after" ] || die "$inflight/after exists: the after is taken once"
  (cd "$inflight" && shasum -a 256 -c SHA256SUMS >/dev/null) || die "the before does not match its sums"
  local new
  new=$(recorded after_commit)
  same_tree "$new" indexer/aidd_indexer "$home/indexer/aidd_indexer" \
    || die "the installed code is not ${new:0:7}'s: the author reinstalls from main first"
  runs_since "$(recorded before_done_at)" > "$inflight/indexruns-after-before-picture.txt"
  builds > "$inflight/builds-after.txt"
  local pending stale failed moved
  if shapes_changed "$(recorded before_commit)" "$new"; then
    pending=$(summary not-reindexed "$inflight")
    [ "$pending" = 0 ] || die "$pending snapshot(s) have no ok last run since the before: wait for the refresh, then run again"
    stale=$(summary stale-builds "$inflight")
    [ "$stale" = 0 ] || die "$stale snapshot(s) still hold the before's build: wait for the refresh, then run again"
  else
    failed=$(summary failed-runs "$inflight")
    [ "$failed" = 0 ] || die "$failed snapshot(s) last ran since the before not ok"
    moved=$(summary moved-builds "$inflight")
    [ "$moved" = 0 ] || die "$moved snapshot(s) hold a build other than the before's, though the change shapes no graph"
  fi
  "$V/graph-picture.sh" "$inflight/after" > "$inflight/picture_after.txt"
  python3 -I "$V/golden.py" "$calls" "$inflight/after/golden" > "$inflight/golden_after.txt"
  python3 -I "$V/graph_vs_dry.py" "$inflight/before" "$inflight/after" "$inflight/dry" > "$inflight/graph_vs_dry.before-after.txt"
  for f in "$inflight"/before/golden/*.json; do
    echo "=== $(basename "$f")"
    python3 -I "$V/json_paths_diff.py" "$f" "$inflight/after/golden/$(basename "$f")"
  done > "$inflight/golden-before-after.paths.txt"
  (cd "$inflight" && { find after -type f | sort | xargs shasum -a 256
    shasum -a 256 picture_after.txt golden_after.txt graph_vs_dry.before-after.txt golden-before-after.paths.txt \
      indexruns-after-before-picture.txt builds-after.txt; } > SHA256SUMS.after)
  echo "sealed: $inflight/SHA256SUMS.after"
  summary after "$inflight"
}

rotate() {
  [ "${1:-}" = "--yes" ] || die "rotate deletes $live/merged and makes inflight/ the new merged/: run it again with --yes"
  [ -d "$inflight/after" ] || die "$inflight has no after: the PR is not validated yet"
  (cd "$inflight" && shasum -a 256 -c SHA256SUMS >/dev/null && shasum -a 256 -c SHA256SUMS.after >/dev/null) \
    || die "the before or the after does not match its sums"
  rm -rf "$inflight"/snap.* "$inflight/main_src" "$inflight/head_src" "$live/merged"
  mv "$inflight" "$live/merged"
  echo "merged/ holds the validated pair; inflight/ is free for the next PR"
}

mode="${1:-}"; [ $# -eq 0 ] || shift
case "$mode" in
  before) before "$@" ;;
  after) after ;;
  rotate) rotate "$@" ;;
  *) sed -n '2,16p' "$0" >&2; exit 2 ;;
esac
