"""The call sites that lost an edge to an extension method of the repo between two dry-runs: the old edge's strategy,
the type the extension's `this` takes, and what the site has now.   ext_sites.py BEFORE AFTER OUT.jsonl REPO..."""
import collections
import json
import re
import sys

sys.path.insert(0, sys.argv[0].rsplit("/", 1)[0])
from edges_lib import edges, load  # noqa: E402

before, after, out = sys.argv[1], sys.argv[2], open(sys.argv[3], "w")
kinds = collections.Counter()
for repo in sys.argv[4:]:
    b, a = load(before, repo), load(after, repo)
    sig = {s["qualified_name"]: s.get("signature") or "" for s in b["symbols"] + a["symbols"]
           if s.get("kind") == "method" and "(this " in (s.get("signature") or "")}
    eb, ea = edges(b), edges(a)
    for site in eb.keys() | ea.keys():
        was, now = eb.get(site, set()), ea.get(site, set())
        gone = {(c, s) for c, s in was - now if c in sig and c not in {x for x, _ in now}}
        for callee, strat in gone:
            m = re.search(r"\(this\s+([\w.<>\[\]?, ]+?)\s+\w+\s*[,)]", sig[callee])
            this = m.group(1) if m else "?"
            kind = ("generic" if re.fullmatch(r"T\w*", this) else "object" if this == "object" else
                    "interface" if re.match(r"I[A-Z]", this) else "class")
            kinds[(strat.replace("-ambiguous", "~"), kind)] += 1
            out.write(json.dumps({"repo": repo, "site": site, "callee": callee, "was": strat, "this": this,
                                  "kind": kind, "now": sorted(now)}) + "\n")
for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
    print(v, *k)
print("all", sum(kinds.values()))
