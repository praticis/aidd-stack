"""The live graph's symbols, CALLS, EXTENDS, IMPLEMENTS and OVERRIDES against the dry-runs, per snapshot: a symbol by
its id, with every property the writer gives it; a CALLS edge by its key in the graph (caller, callee, line, method),
its strategy, `virtual` and `receivers` compared too; and an override's `receivers`. Before the reinstall, the graph
against main's dry-run; after it, the graph after against head's, and what changed against what the dry-runs change.
Prints counts only, with the snapshot as a number, never its name.

usage: graph_vs_dry.py BEFORE_DIR [AFTER_DIR] DRY_DIR"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

*pictures, dry = map(Path, sys.argv[1:])
before, after = pictures[0], pictures[1] if len(pictures) > 1 else None
BOOLEAN = {"TRUE": True, "FALSE": False, "NULL": None}
PROPERTIES = ("kind", "line_start", "line_end", "role", "is_entry_point", "name", "qualified_name", "visibility",
              "content_hash")
ENCODED = ("signature", "doc")


def receivers(joined: str) -> tuple[str, ...]:
    return tuple(t for t in joined.split("|") if t)


def snapshot(node_id: str) -> str:
    return node_id.split("/sym/")[0].split("/file/")[0]


def cell(v) -> str:
    """A value as the picture prints it."""
    return "NULL" if v is None else str(v).upper() if isinstance(v, bool) else str(v)


def graph(d: Path) -> tuple[dict, dict, dict]:
    calls, types, symbols = defaultdict(dict), defaultdict(set), defaultdict(dict)
    with (d / "calls_edges.txt").open() as fh:
        for a, b, line, strategy, _, method, virtual, on in csv.reader(fh, skipinitialspace=True):
            calls[snapshot(a)][(a, b, int(line), None if method == "NULL" else method)] = \
                (strategy, BOOLEAN[virtual], receivers(on))
    with (d / "hierarchy_edges.txt").open() as fh:
        for a, kind, b, on in csv.reader(fh, skipinitialspace=True):
            types[snapshot(a)].add((a, kind, b, receivers(on)))
    if (d / "symbols.txt").exists():
        with (d / "symbols.txt").open() as fh:
            for i, *row in csv.reader(fh, skipinitialspace=True):
                symbols[snapshot(i)][i] = (*row[:len(PROPERTIES)], *map(unquote, row[len(PROPERTIES):]))
    return calls, types, symbols


def dryrun(f: Path) -> tuple[dict, set, dict]:
    run = json.loads(f.read_text())
    symbols = defaultdict(set)
    for s in run.get("symbols", []):
        symbols[s["id"]].add((*(cell(s.get(k)) for k in PROPERTIES), *(s.get(k) or "" for k in ENCODED)))
    return ({(c["caller_id"], c["callee_id"], c["line"], c["method"]):
             (c["strategy"], c.get("virtual"), tuple(c.get("receivers", ()))) for c in run["calls"]},
            {(e["source_id"], e["kind"], e["target_id"], tuple(e.get("receivers", ())))
             for e in run.get("hierarchy", [])}, symbols)


def holds(graph_symbols: dict, dry_symbols: dict) -> bool:
    """The graph holds each of the dry-run's symbols, and no other, with the properties of one record of its id."""
    return graph_symbols.keys() == dry_symbols.keys() and all(v in dry_symbols[i] for i, v in graph_symbols.items())


def changes(b: dict, a: dict, m: dict, h: dict) -> tuple[str, dict[str, bool]]:
    """What the reinstall changed in the graph's CALLS, against what head's dry-run changes from main's."""
    counts = (f"graph {len(b)} -> {len(a)} (-{len(set(b) - set(a))} +{len(set(a) - set(b))}, strategy, virtual or "
              f"receivers changed {sum(1 for k in set(a) & set(b) if a[k] != b[k])}); dry {len(m)} -> {len(h)}")
    return counts, {
        "after = head": set(a) == set(h),
        "removed = main - head": set(b) - set(a) == set(m) - set(h),
        "added = head - main": set(a) - set(b) == set(h) - set(m),
        "strategies, virtual and receivers after = head": all(a[k] == h[k] for k in a if k in h),
    }


(gb, tb, sb), (ga, ta, sa) = graph(before), graph(after) if after else ({}, {}, {})
bad = 0
for i, mf in enumerate(sorted(dry.glob("*__main.json")), 1):
    tenant, repo, ref, _ = mf.stem.split("__")
    snap = f"{tenant}/{repo}@{ref}"
    (m, mt, ms), b, bs = dryrun(mf), gb.get(snap, {}), sb.get(snap, {})
    counts, checks = f"graph {len(b)}; dry {len(m)}; hierarchy {len(tb.get(snap, ()))}; symbols {len(bs)}", {}
    if after:
        h, ht, hs = dryrun(mf.with_name(mf.name.replace("__main.json", "__head.json")))
        a_s = sa.get(snap, {})
        counts, checks = changes(b, ga.get(snap, {}), m, h)
        counts += (f"; hierarchy {len(tb.get(snap, ()))} -> {len(ta.get(snap, ()))}, dry {len(mt)} -> {len(ht)}"
                   f"; symbols {len(bs)} -> {len(a_s)}, changed {sum(a_s[i] != bs[i] for i in a_s.keys() & bs.keys())},"
                   f" dry changed {sum(hs[i] != ms[i] for i in hs.keys() & ms.keys())}")
        checks |= {"hierarchy after = head": ta.get(snap, set()) == ht, "symbols after = head": holds(a_s, hs)}
    checks = {"before = main": set(b) == set(m),
              "strategies, virtual and receivers before = main": all(b[k] == m[k] for k in b if k in m),
              "hierarchy before = main": tb.get(snap, set()) == mt, "symbols before = main": holds(bs, ms), **checks}
    ok = all(checks.values())
    bad += not ok
    print(f"snapshot {i}: {counts}; "
          + ("all match" if ok else "MISMATCH: " + ", ".join(k for k, v in checks.items() if not v)))
print(f"\nmismatching snapshots: {bad}")
sys.exit(1 if bad else 0)
