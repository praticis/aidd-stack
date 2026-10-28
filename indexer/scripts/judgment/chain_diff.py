"""The CALLS edges that differ between two dry-runs of each repo, per strategy class (typed, inherited, by name,
by name and ambiguous) and per kind of site change (same callees by another strategy, callees added, dropped, widened,
narrowed or changed), with seeded samples of the kinds that change a callee.
   chain_diff.py BEFORE_DIR AFTER_DIR SAMPLE REPO... > OUT   (samples as JSON lines on stderr)"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edges_lib import changed, kind, load  # noqa: E402


def cls(strategy: str) -> str:
    amb = "~amb" if "ambiguous" in strategy else ""
    if strategy.startswith("receiver-type"):
        return "typed" + amb
    return ("inherited" if strategy.startswith("inherited") else "name") + amb


before, after, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
rng = random.Random(20261021)
total, kinds, pick = collections.Counter(), collections.Counter(), collections.defaultdict(list)
for repo in sys.argv[4:]:
    per = collections.Counter()
    for key, was, now in changed(load(before, repo), load(after, repo)):
        k = kind(was, now)
        kinds[k] += 1
        per[k] += 1
        for e in was - now:
            total[("removed", cls(e[1]))] += 1
        for e in now - was:
            total[("added", cls(e[1]))] += 1
        if k != "strategy":
            pick[k].append({"repo": repo, "file": key[0], "line": key[1], "was": sorted(was), "now": sorted(now)})
    print(f"{repo}: " + (", ".join(f"{k} {c}" for k, c in sorted(per.items())) or "no edge differs"))
print("\nsites by kind:", dict(sorted(kinds.items())))
for k in sorted(total):
    print(f"  {k[0]:8} {k[1]:13} {total[k]}")
for k, items in sorted(pick.items()):
    for it in rng.sample(items, min(n, len(items))):
        print(json.dumps({"kind": k, **it}), file=sys.stderr)
