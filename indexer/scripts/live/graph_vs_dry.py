"""The live graph's CALLS before and after a reinstall against the dry-runs of main and head, per snapshot, by the
graph's merge key (caller, callee, line). Prints counts only, with the snapshot as a number, never its name.

usage: graph_vs_dry.py BEFORE_DIR AFTER_DIR DRY_DIR"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

before, after, dry = map(Path, sys.argv[1:4])


def graph(d: Path) -> dict:
    by = defaultdict(dict)
    with (d / "calls_edges.txt").open() as fh:
        for a, b, line, strategy, *_ in csv.reader(fh, skipinitialspace=True):
            snap = a.split("/sym/")[0].split("/file/")[0]
            by[snap][(a, b, int(line))] = strategy
    return by


def dryrun(f: Path) -> dict:
    return {(c["caller_id"], c["callee_id"], c["line"]): c["strategy"] for c in json.loads(f.read_text())["calls"]}


gb, ga = graph(before), graph(after)
bad = 0
for i, mf in enumerate(sorted(dry.glob("*__main.json")), 1):
    tenant, repo, ref, _ = mf.stem.split("__")
    snap = f"{tenant}/{repo}@{ref}"
    m, h = dryrun(mf), dryrun(mf.with_name(mf.name.replace("__main.json", "__head.json")))
    b, a = gb.get(snap, {}), ga.get(snap, {})
    checks = {
        "before = main": set(b) == set(m),
        "after = head": set(a) == set(h),
        "removed = main - head": set(b) - set(a) == set(m) - set(h),
        "added = head - main": set(a) - set(b) == set(h) - set(m),
        "strategies after = head": all(a[k] == h[k] for k in a if k in h),
    }
    ok = all(checks.values())
    bad += not ok
    print(f"snapshot {i}: graph {len(b)} -> {len(a)} (-{len(set(b) - set(a))} +{len(set(a) - set(b))}, "
          f"strategy changed {sum(1 for k in set(a) & set(b) if a[k] != b[k])}); dry {len(m)} -> {len(h)}; "
          + ("all match" if ok else "MISMATCH: " + ", ".join(k for k, v in checks.items() if not v)))
print(f"\nmismatching snapshots: {bad}")
sys.exit(1 if bad else 0)
