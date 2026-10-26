"""Of the extension-method edges a run lost against main (ext_sites.py's rows), which a later run has again, by what
strategy, and what the rest of the sites have instead.   ext_back.py LOST.jsonl AFTER_DIR OUT.jsonl"""
import collections
import json
import sys

sys.path.insert(0, sys.argv[0].rsplit("/", 1)[0])
from edges_lib import edges, load  # noqa: E402

rows = [json.loads(line) for line in open(sys.argv[1])]
out = open(sys.argv[3], "w")
runs = {}
count = collections.Counter()
for r in rows:
    if r["repo"] not in runs:
        runs[r["repo"]] = edges(load(sys.argv[2], r["repo"]))
    now = runs[r["repo"]].get(tuple(r["site"]), set())
    back = [s for c, s in now if c == r["callee"]]
    state = "back " + back[0].replace("-ambiguous", "~") if back else "lost, now " + (
        "nothing" if not now else "inherited" if all(s == "inherited" for _, s in now) else
        "typed" if any(s.startswith("receiver-type") for _, s in now) else "name")
    count[(state, r["kind"])] += 1
    out.write(json.dumps(r | {"c7": sorted(now), "state": state}) + "\n")
for k, v in sorted(count.items(), key=lambda kv: (kv[0][0], -kv[1])):
    print(v, *k)
print("all", sum(count.values()))
