"""main's and head's dry-runs of each live snapshot, section by section: the records that differ, with the snapshot as
a number, CALLS by strategy and the CALLS that do not dispatch. No name leaves this script.   dry_sections.py DRY_DIR"""
import collections
import json
import sys
from pathlib import Path

KEYS = {"files": ("path",), "symbols": ("id",), "calls": ("caller_id", "callee_id", "line", "strategy"),
        "imports": ("file_id", "target_id", "spec"), "hierarchy": ("source_id", "kind", "target_id"),
        "endpoints": ("method", "path", "file_id", "line"),
        "http_calls": ("method", "path", "file_id", "line")}
dry = Path(sys.argv[1])
for n, main in enumerate(sorted(dry.glob("*__main.json")), 1):
    a, b = json.load(open(main)), json.load(open(str(main).replace("__main.json", "__head.json")))
    out = []
    for sec, key in KEYS.items():
        ka = collections.Counter(tuple(r.get(k) for k in key) for r in a.get(sec, []))
        kb = collections.Counter(tuple(r.get(k) for k in key) for r in b.get(sec, []))
        if ka != kb:
            out.append(f"{sec} -{sum((ka - kb).values())} +{sum((kb - ka).values())}")
    direct = [sum(c.get("virtual") is False for c in run["calls"]) for run in (a, b)]
    if direct[0] != direct[1]:
        out.append(f"not dispatching {direct[0]} -> {direct[1]}")
    calls = ""
    if any(o.startswith("calls") for o in out):
        sa = collections.Counter(c["strategy"] for c in a["calls"])
        sb = collections.Counter(c["strategy"] for c in b["calls"])
        calls = " | by strategy " + ", ".join(f"{s} {sb[s] - sa[s]:+d}" for s in sorted(sa | sb) if sb[s] != sa[s])
    langs = collections.Counter(f.get("language") for f in a.get("files", []))
    print(f"snapshot {n} ({', '.join(f'{lang} {c}' for lang, c in langs.most_common(2))}): "
          + ("identical" if not out else "; ".join(out)) + calls)
