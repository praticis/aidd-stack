"""Each CALLS edge that differs between two dry-runs of a repo, by the case the call's site has in why_a's output; an
edge whose site has none is unexplained. Seeded samples per case and repo, for judging at the source.
   edges_join.py BASE_DIR HEAD_DIR WHY.jsonl SAMPLE REPO..."""
import collections
import gzip
import json
import random
import sys


def load(d, repo):
    return json.load(gzip.open(f"{d}/{repo}.json.gz", "rt"))


def edges(run):
    files = {f["id"]: f["path"] for f in run["files"]}
    sym = {s["id"]: s for s in run["symbols"]}
    out = {}
    for c in run["calls"]:
        caller = sym.get(c["caller_id"])
        f = files.get(caller["file_id"]) if caller else None
        if f is None:                                  # a call from a file, not from a symbol
            f = files.get(c["caller_id"], "?")
        callee = sym.get(c["callee_id"], {}).get("qualified_name", c["callee_id"])
        out.setdefault((f, c["line"]), set()).add((callee, c["strategy"]))
    return out


base, head, why, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
sites = collections.defaultdict(dict)
for line in open(why):
    d = json.loads(line)
    if "case" in d:
        sites[d["repo"]][(d["file"], d["line"])] = d
rng = random.Random(20261021)
for repo in sys.argv[5:]:
    b, h = edges(load(base, repo)), edges(load(head, repo))
    per = collections.defaultdict(list)
    for key in sorted(set(b) | set(h)):
        if b.get(key, set()) == h.get(key, set()):
            continue
        site = sites[repo].get(key)
        per[site["case"] if site else "unexplained"].append((key, sorted(b.get(key, ())), sorted(h.get(key, ())), site))
    print(f"== {repo}: " + ", ".join(f"{k} {len(v)}" for k, v in sorted(per.items())) if per else f"== {repo}: no edge differs")
    for case, items in sorted(per.items()):
        for key, was, now, site in rng.sample(items, min(n, len(items))) if case != "unexplained" else items[:20]:
            print(f"  [{case}] {key[0]}:{key[1]}  {site['src'] if site else ''}")
            print(f"      was {was}\n      now {now}" + (f"\n      type {site['old']} -> {site['new']}" if site else ""))
