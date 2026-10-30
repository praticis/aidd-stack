#!/usr/bin/env bash
# The live check before a merge: each live snapshot exported at its sha (git archive, as the refresher does) and indexed
# with --dry-run by main's code and by the branch's. Reads the snapshot list from the before picture; prints each
# snapshot as a number.   dryrun-live.sh SCRATCH HEAD_INDEXER MAIN_INDEXER LIVE_DIR
set -uo pipefail
S="$1"; head_code="$2"; main_code="$3"; L="$4"
out="$L/dry"; mkdir -p "$out"
# a folder no earlier run used: an IDE that loaded a project of an earlier copy writes its build output back to its path
snap=$(mktemp -d "$L/snap.XXXXXX")
n=0; bad=0
while IFS= read -r line; do
  n=$((n + 1))
  tenant=$(echo "$line" | awk -F'"' '{print $2}'); repo=$(echo "$line" | awk -F'"' '{print $4}')
  ref=$(echo "$line" | awk -F'"' '{print $6}'); sha=$(echo "$line" | awk -F'"' '{print $8}')
  dest="$snap/$tenant/$ref/$repo"; src="$HOME/workspace/$tenant/$repo"
  mkdir -p "$dest" && git -C "$src" archive "$sha" | tar -x -C "$dest" \
    || { echo "snapshot $n: archive failed"; bad=1; continue; }
  absent=$(git -C "$src" ls-tree -r -z --name-only "$sha" \
    | while IFS= read -r -d '' f; do [ -e "$dest/$f" ] || [ -L "$dest/$f" ] || echo; done | wc -l | tr -d ' ')
  [ "$absent" = 0 ] || { echo "snapshot $n: $absent file(s) of its sha missing from the copy"; bad=1; continue; }
  for v in main head; do
    code=$([ "$v" = main ] && echo "$main_code" || echo "$head_code")
    f="$out/${tenant}__${repo}__${ref}__${v}.json"
    t0=$(date +%s)
    docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH=/code -e PYTHONDONTWRITEBYTECODE=1 \
      -e AIDD_TENANT="$tenant" -e AIDD_CONFIG=/app/atlas.yaml \
      -v "$code":/code:ro -v "$snap/$tenant/$ref":/snap:ro -v "$HOME/.aidd/atlas.yaml":/app/atlas.yaml:ro -v "$out":/out \
      -w /code --entrypoint python aidd-indexer:local -m aidd_indexer.cli index "/snap/$repo" --tenant "$tenant" \
      --ref "$ref" --dry-run --out "/out/$(basename "$f")" > "$f.log" 2>&1
    echo "snapshot $n $v rc=$? $(( $(date +%s) - t0 ))s"
  done
done < "$L/before/snapshots.txt"
exit $bad
