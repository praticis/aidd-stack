"""No win reverted. For every saved run (corpus baselines and hold-out runs, oldest first), the gabarito pairs
(today's gabaritos) it finds; a pair some run found and the final run misses is reported.

usage: a5_chain.py RUNS_DIR GABARITO_DIR CORPUS_FINAL HOLDOUT_FINAL"""
import json
import os
import re
import sys
from pathlib import Path

from corpus_metrics import KINDS, score

runs_dir, gab_dir = Path(sys.argv[1]), Path(sys.argv[2])
corpus_final, holdout_final = sys.argv[3], sys.argv[4]

gabs = {p.stem: json.loads(p.read_text()) for p in gab_dir.glob("*.json")}
gabs |= {p.stem: json.loads(p.read_text()) for p in (gab_dir / "holdout").glob("*.json")}
holdout_repos = {p.stem for p in (gab_dir / "holdout").glob("*.json")}

names = [d.name for d in runs_dir.iterdir() if d.is_dir() and not d.name.endswith(".logs")
         and re.search(r"v2-baseline|holdout", d.name) and "validate" not in d.name]
names.sort(key=lambda n: os.stat(runs_dir / n).st_mtime)


def found(run: dict, gab: dict, kind: str) -> set:
    sc = score(run, gab, kind)
    if sc is None:
        return set()
    from corpus_metrics import item_key
    return {item_key(i) for i in gab[kind]} - set(sc.false_negatives)


lost_total = 0
for repo, gab in sorted(gabs.items()):
    final_name = holdout_final if repo in holdout_repos else corpus_final
    final_path = runs_dir / final_name / f"{repo}.json"
    if not final_path.exists():
        print(f"{repo}: no final run")
        continue
    final = json.loads(final_path.read_text())
    seen: dict[tuple, str] = {}
    runs = 0
    for n in names:
        p = runs_dir / n / f"{repo}.json"
        if not p.exists() or n == final_name:
            continue
        runs += 1
        run = json.loads(p.read_text())
        for kind in KINDS:
            for k in found(run, gab, kind):
                seen[(kind, k)] = n
    final_found = {(kind, k) for kind in KINDS for k in found(final, gab, kind)}
    lost = sorted(set(seen) - final_found)
    lost_total += len(lost)
    cats = {(kind, __import__("corpus_metrics").item_key(i)): i.get("category") for kind in KINDS for i in gab.get(kind, []) or []}
    print(f"{repo}: {runs} earlier runs, {len(final_found)} pairs found at the end, {len(lost)} lost")
    for kind, k in lost:
        print(f"    LOST {kind} {k} last found in {seen[(kind, k)]} category={cats.get((kind, k))}")
print(f"\nlost pairs in total: {lost_total}")
