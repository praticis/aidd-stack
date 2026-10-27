"""No win reverted. For every saved run (corpus baselines and hold-out runs, oldest first), the pairs of today's
expected lists it finds; a pair some run found and the final run misses is reported.

usage: expected_lists_chain.py RUNS_DIR LISTS_DIR CORPUS_FINAL HOLDOUT_FINAL
Needs corpus_metrics and aidd_indexer importable: in the indexer image, PYTHONPATH=/src:/src/scripts."""
import json
import os
import re
import sys
from pathlib import Path

from corpus_metrics import KINDS, item_key, score

runs_dir, lists_dir = Path(sys.argv[1]), Path(sys.argv[2])
corpus_final, holdout_final = sys.argv[3], sys.argv[4]

lists = {p.stem: json.loads(p.read_text()) for p in lists_dir.glob("*.json")}
lists |= {p.stem: json.loads(p.read_text()) for p in (lists_dir / "holdout").glob("*.json")}
holdout_repos = {p.stem for p in (lists_dir / "holdout").glob("*.json")}

names = [d.name for d in runs_dir.iterdir() if d.is_dir() and not d.name.endswith(".logs")
         and re.search(r"v2-baseline|holdout", d.name) and "validate" not in d.name]
names.sort(key=lambda n: os.stat(runs_dir / n).st_mtime)


def found(run: dict, expected: dict, kind: str) -> set:
    sc = score(run, expected, kind)
    if sc is None:
        return set()
    return {item_key(i) for i in expected[kind]} - set(sc.false_negatives)


lost_total = 0
for repo, expected in sorted(lists.items()):
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
            for k in found(run, expected, kind):
                seen[(kind, k)] = n
    final_found = {(kind, k) for kind in KINDS for k in found(final, expected, kind)}
    lost = sorted(set(seen) - final_found)
    lost_total += len(lost)
    cats = {(kind, item_key(i)): i.get("category") for kind in KINDS for i in expected.get(kind, []) or []}
    print(f"{repo}: {runs} earlier runs, {len(final_found)} pairs found at the end, {len(lost)} lost")
    for kind, k in lost:
        print(f"    LOST {kind} {k} last found in {seen[(kind, k)]} category={cats.get((kind, k))}")
print(f"\nlost pairs in total: {lost_total}")
