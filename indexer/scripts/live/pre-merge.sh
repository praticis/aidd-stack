#!/usr/bin/env bash
# The live check before a merge, read-only: the picture and the golden answers now, then main's and the branch's
# dry-runs of every snapshot, compared. LIVE_DIR holds main_src/indexer and head_src/indexer, copies of the two
# codes; everything it writes goes next to them, outside the repository.
#   pre-merge.sh LIVE_DIR GOLDEN_CALLS_JSON
V="$(cd "$(dirname "$0")" && pwd)"
L="$1"; calls="$2"
"$V/graph-picture.sh" "$L/before" > "$L/picture_before.txt" 2>&1; echo "picture rc=$?"
python3 -I "$V/golden.py" "$calls" "$L/before/golden" > "$L/golden_before.txt" 2>&1; echo "golden rc=$?"
"$V/dryrun-live.sh" "$L" "$L/head_src/indexer" "$L/main_src/indexer" "$L" > "$L/dryrun.txt" 2>&1; echo "dryrun rc=$?"
python3 -I "$V/dry_sections.py" "$L/dry" > "$L/dry_sections.txt" 2>&1; echo "sections rc=$?"
python3 -I "$V/graph_vs_dry.py" "$L/before" "$L/before" "$L/dry" > "$L/graph_vs_dry.txt" 2>&1; echo "graph rc=$?"
