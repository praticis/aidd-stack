"""The live graph's CALLS, EXTENDS and IMPLEMENTS against the dry-runs, per snapshot: a CALLS edge by its key in the
graph (caller, callee, line, method), its strategy and `virtual` compared too. Before the reinstall, the graph against
main's dry-run; after it, the graph after against head's, and what changed against what the dry-runs change. Prints
counts only, with the snapshot as a number, never its name.

usage: graph_vs_dry.py BEFORE_DIR [AFTER_DIR] DRY_DIR"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

*pictures, dry = map(Path, sys.argv[1:])
before, after = pictures[0], pictures[1] if len(pictures) > 1 else None
BOOLEAN = {"TRUE": True, "FALSE": False, "NULL": None}


def snapshot(node_id: str) -> str:
    return node_id.split("/sym/")[0].split("/file/")[0]


def graph(d: Path) -> tuple[dict, dict]:
    calls, types = defaultdict(dict), defaultdict(set)
    with (d / "calls_edges.txt").open() as fh:
        for a, b, line, strategy, _, method, virtual in csv.reader(fh, skipinitialspace=True):
            calls[snapshot(a)][(a, b, int(line), None if method == "NULL" else method)] = (strategy, BOOLEAN[virtual])
    with (d / "hierarchy_edges.txt").open() as fh:
        for a, kind, b in csv.reader(fh, skipinitialspace=True):
            types[snapshot(a)].add((a, kind, b))
    return calls, types


def dryrun(f: Path) -> tuple[dict, set]:
    run = json.loads(f.read_text())
    return ({(c["caller_id"], c["callee_id"], c["line"], c["method"]): (c["strategy"], c.get("virtual"))
             for c in run["calls"]},
            {(e["source_id"], e["kind"], e["target_id"]) for e in run.get("hierarchy", [])})


def changes(b: dict, a: dict, m: dict, h: dict) -> tuple[str, dict[str, bool]]:
    """What the reinstall changed in the graph's CALLS, against what head's dry-run changes from main's."""
    counts = (f"graph {len(b)} -> {len(a)} (-{len(set(b) - set(a))} +{len(set(a) - set(b))}, strategy or virtual "
              f"changed {sum(1 for k in set(a) & set(b) if a[k] != b[k])}); dry {len(m)} -> {len(h)}")
    return counts, {
        "after = head": set(a) == set(h),
        "removed = main - head": set(b) - set(a) == set(m) - set(h),
        "added = head - main": set(a) - set(b) == set(h) - set(m),
        "strategies and virtual after = head": all(a[k] == h[k] for k in a if k in h),
    }


(gb, tb), (ga, ta) = graph(before), graph(after) if after else ({}, {})
bad = 0
for i, mf in enumerate(sorted(dry.glob("*__main.json")), 1):
    tenant, repo, ref, _ = mf.stem.split("__")
    snap = f"{tenant}/{repo}@{ref}"
    (m, mt), b = dryrun(mf), gb.get(snap, {})
    counts, checks = f"graph {len(b)}; dry {len(m)}; types {len(tb.get(snap, ()))}", {}
    if after:
        h, ht = dryrun(mf.with_name(mf.name.replace("__main.json", "__head.json")))
        counts, checks = changes(b, ga.get(snap, {}), m, h)
        counts += f"; types {len(tb.get(snap, ()))} -> {len(ta.get(snap, ()))}, dry {len(mt)} -> {len(ht)}"
        checks["types after = head"] = ta.get(snap, set()) == ht
    checks = {"before = main": set(b) == set(m),
              "strategies and virtual before = main": all(b[k] == m[k] for k in b if k in m),
              "types before = main": tb.get(snap, set()) == mt, **checks}
    ok = all(checks.values())
    bad += not ok
    print(f"snapshot {i}: {counts}; "
          + ("all match" if ok else "MISMATCH: " + ", ".join(k for k, v in checks.items() if not v)))
print(f"\nmismatching snapshots: {bad}")
sys.exit(1 if bad else 0)
