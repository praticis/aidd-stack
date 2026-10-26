"""For each site where a run gained a `unique-name` edge to an extension method, what that extension's `this` takes,
read in its source: any value (a type parameter, `object`) or a named type.   this_kind.py BEFORE AFTER REPOS REPO..."""
import collections
import gzip
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[0].rsplit("/", 1)[0])
from edges_lib import edges, load  # noqa: E402

before, after, repos = sys.argv[1], sys.argv[2], Path(sys.argv[3])
groups = collections.defaultdict(list)
for repo in sys.argv[4:]:
    b, a = load(before, repo), load(after, repo)
    files = {f["id"]: f["path"] for f in a["files"]}
    sym = {s["qualified_name"]: s for s in a["symbols"]}
    eb, ea = edges(b), edges(a)
    for site, now in ea.items():
        for callee, strat in now - eb.get(site, set()):
            if strat != "unique-name" or callee not in sym:
                continue
            s = sym[callee]
            lines = (repos / repo / files[s["file_id"]]).read_text(errors="replace").splitlines()
            head = " ".join(lines[s["line_start"] - 1:s["line_start"] + 4])
            m = re.search(r"\(\s*(?:\[[^\]]*\]\s*)*this\s+([^,)]+?)\s+\w+\s*[,)=]", head)
            this = m.group(1) if m else "?"
            tps = re.search(r"\b" + re.escape(s["name"]) + r"\s*<([^>(]*)>\s*\(", head)
            own = {t.strip() for t in tps.group(1).split(",")} if tps else set()
            kind = "any" if this.rstrip("?") in own or this.rstrip("?") == "object" else "type"
            src = (repos / repo / site[0]).read_text(errors="replace").splitlines()[site[1] - 1].strip()[:110]
            groups[kind].append((repo, site, callee.split(".")[-2] + "." + s["name"], this, src))
for kind, rows in groups.items():
    print(f"== {kind}: {len(rows)}")
    for repo, site, callee, this, src in sorted(rows):
        print(f"  {repo} {site[0].split('/')[-1]}:{site[1]} {callee}(this {this})\n      {src}")
