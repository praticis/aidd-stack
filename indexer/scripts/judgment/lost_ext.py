"""Edges a site loses between two dry-runs whose callee lives in a file with C# 14 `extension(...)` blocks, per repo,
and how many of those sites keep no edge at all.   lost_ext.py BEFORE AFTER REPOS_DIR REPO..."""
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[0].rsplit("/", 1)[0])
from edges_lib import load  # noqa: E402

BLOCK = re.compile(r"^\s*extension(<[^>]*>)?\s*\(", re.M)
before, after, repos = sys.argv[1], sys.argv[2], Path(sys.argv[3])
for repo in sys.argv[4:]:
    runs = [load(d, repo) for d in (before, after)]
    has_block = {}

    def blocky(path):
        if path not in has_block:
            try:
                has_block[path] = bool(BLOCK.search((repos / repo / path).read_text(errors="replace")))
            except OSError:
                has_block[path] = False
        return has_block[path]

    sides = []
    for run in runs:
        files = {f["id"]: f["path"] for f in run["files"]}
        sym = {s["id"]: s for s in run["symbols"]}
        out = collections.defaultdict(set)
        for c in run["calls"]:
            caller, callee = sym.get(c["caller_id"]), sym.get(c["callee_id"])
            if caller is None or callee is None:
                continue
            out[(files[caller["file_id"]], c["line"])].add((callee["qualified_name"], files[callee["file_id"]]))
        sides.append(out)
    b, h = sides
    lost, emptied = 0, 0
    for key, was in b.items():
        now = h.get(key, set())
        gone = [e for e in was - now if blocky(e[1])]
        lost += bool(gone)
        emptied += bool(gone) and not now
    print(f"{repo}: sites losing an edge into a file with extension blocks {lost}, left with none {emptied}")
