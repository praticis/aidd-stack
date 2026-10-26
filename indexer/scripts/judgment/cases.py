import json, sys, collections
rows = [json.loads(l) for l in open(sys.argv[1])]
by = collections.Counter(r["case"] for r in rows)
print("total", len(rows)); [print(f"  {c}: {n}") for c, n in by.most_common()]
per = collections.defaultdict(collections.Counter)
for r in rows: per[r["repo"]][r["case"]] += 1
for repo, c in per.items(): print(repo, dict(c))
ways = collections.Counter((r["case"], r["way"], r["old"] is None, r["new"] is None) for r in rows)
print("case, old way, old None, new None:")
for k, n in ways.most_common(): print("  ", k, n)
