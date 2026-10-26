"""Each changed CALLS edge site by case and kind: the same callees by another strategy, callees added, callees lost, or
callees changed. Seeded samples of the kinds that change a callee.   kinds.py BASE HEAD WHY.jsonl SAMPLE REPO..."""
import collections
import json
import random
import sys

sys.path.insert(0, sys.argv[0].rsplit("/", 1)[0])
from edges_lib import edges, load  # noqa: E402

base, head, why, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
sites = collections.defaultdict(dict)
for line in open(why):
    d = json.loads(line)
    if "case" in d:
        sites[d["repo"]][(d["file"], d["line"])] = d
rng = random.Random(20261021)
total = collections.Counter()
pick = collections.defaultdict(list)
for repo in sys.argv[5:]:
    b, h = edges(load(base, repo)), edges(load(head, repo))
    for key in sorted(set(b) | set(h)):
        was, now = b.get(key, set()), h.get(key, set())
        if was == now:
            continue
        cw, cn = {c for c, _ in was}, {c for c, _ in now}
        kind = ("strategy" if cw == cn else "added" if not cw else "dropped" if not cn else "widened" if cw < cn
                else "narrowed" if cn < cw else "changed")
        site = sites[repo].get(key)
        case = site["case"] if site else "unexplained"
        total[(case, kind)] += 1
        pick[(case, kind)].append((repo, key, sorted(was), sorted(now), site))
for (case, kind), c in sorted(total.items()):
    print(f"{case:34} {kind:9} {c}")
print("\ndropped: the strategies they had, and the type the receiver has now")
drop = collections.Counter()
for (case, kind), items in pick.items():
    if kind == "dropped":
        for repo, key, was, now, site in items:
            drop[(tuple(sorted({s for _, s in was})), str((site or {}).get("new", "?")).split("#")[0][:40])] += 1
for k, c in drop.most_common(25):
    print(f"  {c:5} {k}")
for (case, kind), items in sorted(pick.items()):
    if kind == "strategy":
        continue
    for repo, key, was, now, site in rng.sample(items, min(n, len(items))):
        print(f"\n[{case} / {kind}] {repo} {key[0]}:{key[1]}  {site['src'][:110] if site else ''}")
        print(f"   was {was}\n   now {now}" + (f"\n   type {site['old']} -> {site['new']}" if site else ""))
