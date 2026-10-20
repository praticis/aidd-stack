#!/usr/bin/env bash
# A shallow window of a public repo's recent history, ending at a fixed commit, for the H6 step 1 replay.
#   fetch.sh NAME SLUG SHA
set -euo pipefail
R="$HOME/.cache/aidd-corpus/h6/replay"
d="$R/$1-w40.git"
[ -d "$d" ] || { git init -q --bare "$d"; git -C "$d" remote add origin "https://github.com/$2"; }
git -C "$d" fetch -q --depth 40 origin "$3"
git -C "$d" update-ref refs/heads/replay "$3"
echo "$1 $3 fp=$(git -C "$d" rev-list --first-parent --count replay) $(du -sh "$d" | cut -f1)"
