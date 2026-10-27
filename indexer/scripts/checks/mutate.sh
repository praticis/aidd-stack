#!/usr/bin/env bash
# Runs mcp-it.sh on a fresh copy of the tree with one mutation of the writer; prints the failing tests only.
#   mutate.sh NAME PYTHON_REPLACE_OLD PYTHON_REPLACE_NEW
set -uo pipefail
R="$(cd "$(dirname "$0")/../../.." && pwd)"
dst="${AIDD_MUTATE_DIR:-$HOME/.cache/aidd-corpus/mutate}/mut-$1-$(date +%s)"
mkdir -p "$dst/neo4j/init" && cp "$R/neo4j/init/schema.cypher" "$dst/neo4j/init/"
rsync -a --exclude __pycache__ --exclude .pytest_cache "$R/indexer" "$dst/"
OLD="$2" NEW="$3" F="$dst/indexer/aidd_indexer/core/graph.py" python3 -I -c '
import os; p = os.environ["F"]; s = open(p).read(); o, n = os.environ["OLD"], os.environ["NEW"]
assert s.count(o) == 1, f"mutation anchor found {s.count(o)} times"; open(p, "w").write(s.replace(o, n))' || exit 3
"$dst/indexer/scripts/mcp-it.sh" 2>&1 | grep -E "^FAILED|passed|failed|Error" | sed -E 's/ - .*//' | sort | uniq -c | sort -rn | head -20
