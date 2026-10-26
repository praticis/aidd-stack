"""main's dry-run against HEAD's per snapshot, and main's against the live graph's counts.

usage: dry_compare.py DRY_DIR BEFORE_DIR"""
import json
import sys
from pathlib import Path

dry, before = Path(sys.argv[1]), Path(sys.argv[2])
NON_HTTP = ("modules", "files", "symbols", "calls", "imports", "packages", "violations", "provides", "requires")


def canon(items: list) -> list[str]:
    return sorted(json.dumps(i, sort_keys=True, default=str) for i in items)


def ep_key(e: dict) -> tuple:
    return (e["method"], e["path"], e.get("app", ""), e.get("evidence", ""), e.get("handler_name"))


def call_key(c: dict) -> tuple:
    return (c["method"], c["path"], c.get("raw_path"), c.get("evidence", ""), c.get("via"))


graph = {}
for ln in (before / "counts_micro.txt").read_text().splitlines():
    p = [x.strip().strip('"') for x in ln.split(",")]
    graph[(p[0], p[1], p[2])] = dict(zip(("files", "symbols", "calls", "imports", "violations", "http_calls"),
                                         map(int, p[3:9])))
exposes = {}
for ln in (before / "counts_macro.txt").read_text().splitlines():
    p = [x.strip().strip('"') for x in ln.split(",")]
    if p[0] == "EXPOSES":
        exposes[(p[1], p[2], p[3])] = int(p[4])

problems = 0
for mf in sorted(dry.glob("*__main.json")):
    tenant, repo, ref, _ = mf.stem.split("__")
    hf = mf.with_name(mf.name.replace("__main.json", "__head.json"))
    m, h = json.loads(mf.read_text()), json.loads(hf.read_text())
    print(f"== {tenant}/{repo}@{ref}")
    for sec in NON_HTTP:
        a, b = canon(m.get(sec, [])), canon(h.get(sec, []))
        if a != b:
            problems += 1
            print(f"  NON-HTTP DIFF {sec}: main {len(a)} head {len(b)}; -{len(set(a) - set(b))} +{len(set(b) - set(a))}")
    for sec, key in (("endpoints", ep_key), ("http_calls", call_key)):
        a, b = {key(x) for x in m.get(sec, [])}, {key(x) for x in h.get(sec, [])}
        print(f"  {sec}: main {len(m.get(sec, []))} head {len(h.get(sec, []))}")
        for k in sorted(a - b):
            print(f"    - {k}")
        for k in sorted(b - a):
            print(f"    + {k}")
    if m.get("warnings") != h.get("warnings"):
        print(f"  warnings: main {m.get('warnings')} head {h.get('warnings')}")
    g = graph.get((tenant, repo, ref))
    c = m["counts"]
    mine = {"files": len(m["files"]), "symbols": len(m["symbols"]), "calls": c.get("calls_edges"),
            "imports": c.get("imports_edges"), "violations": len(m["violations"]), "http_calls": len(m["http_calls"])}
    if g is not None:
        off = {k: (mine[k], g[k]) for k in g if mine[k] != g[k]}
        ex = exposes.get((tenant, repo, ref), 0)
        if len(m["endpoints"]) != ex:
            off["endpoints"] = (len(m["endpoints"]), ex)
        print(f"  main dry-run vs live graph: {'same counts' if not off else off}")
        problems += bool(off)
print(f"\nproblems: {problems}")
