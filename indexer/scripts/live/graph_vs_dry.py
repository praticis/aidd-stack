"""The live graph's CALLS against the dry-runs, per snapshot, by an edge's key in the graph (caller, callee, line,
method), its strategy compared too: before the reinstall, the graph against main's dry-run; after it, the graph after
against head's, and what changed against what the dry-runs change. Prints counts only, with the snapshot as a number,
never its name.

usage: graph_vs_dry.py BEFORE_DIR [AFTER_DIR] DRY_DIR"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

*pictures, dry = map(Path, sys.argv[1:])
before, after = pictures[0], pictures[1] if len(pictures) > 1 else None


def graph(d: Path) -> dict:
    by = defaultdict(dict)
    with (d / "calls_edges.txt").open() as fh:
        for a, b, line, strategy, _, method in csv.reader(fh, skipinitialspace=True):
            snap = a.split("/sym/")[0].split("/file/")[0]
            by[snap][(a, b, int(line), None if method == "NULL" else method)] = strategy
    return by


def dryrun(f: Path) -> dict:
    return {(c["caller_id"], c["callee_id"], c["line"], c["method"]): c["strategy"]
            for c in json.loads(f.read_text())["calls"]}


def changes(b: dict, a: dict, m: dict, h: dict) -> tuple[str, dict[str, bool]]:
    """What the reinstall changed in the graph, against what head's dry-run changes from main's."""
    counts = (f"graph {len(b)} -> {len(a)} (-{len(set(b) - set(a))} +{len(set(a) - set(b))}, strategy changed "
              f"{sum(1 for k in set(a) & set(b) if a[k] != b[k])}); dry {len(m)} -> {len(h)}")
    return counts, {
        "after = head": set(a) == set(h),
        "removed = main - head": set(b) - set(a) == set(m) - set(h),
        "added = head - main": set(a) - set(b) == set(h) - set(m),
        "strategies after = head": all(a[k] == h[k] for k in a if k in h),
    }


gb, ga = graph(before), graph(after) if after else None
bad = 0
for i, mf in enumerate(sorted(dry.glob("*__main.json")), 1):
    tenant, repo, ref, _ = mf.stem.split("__")
    snap = f"{tenant}/{repo}@{ref}"
    m, b = dryrun(mf), gb.get(snap, {})
    counts, checks = f"graph {len(b)}; dry {len(m)}", {}
    if ga is not None:
        h = dryrun(mf.with_name(mf.name.replace("__main.json", "__head.json")))
        counts, checks = changes(b, ga.get(snap, {}), m, h)
    checks = {"before = main": set(b) == set(m), "strategies before = main": all(b[k] == m[k] for k in b if k in m),
              **checks}
    ok = all(checks.values())
    bad += not ok
    print(f"snapshot {i}: {counts}; "
          + ("all match" if ok else "MISMATCH: " + ", ".join(k for k, v in checks.items() if not v)))
print(f"\nmismatching snapshots: {bad}")
sys.exit(1 if bad else 0)
