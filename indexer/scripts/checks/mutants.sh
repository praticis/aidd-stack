#!/usr/bin/env bash
# Each rule of a change broken once, and the tests asked whether they notice (the whole story is mutants.py's docstring).
#   mutants.sh MUTANTS.py [ID ...] [--allow ID ...] [--tests ARG ...]
# It is one heavy job at a time like the corpus: it takes the heavy-job lock, then runs test.sh once per mutant.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../lib/heavy-lock.sh"
heavy_lock mutants
exec python3 -I "$here/mutants.py" "$@"
