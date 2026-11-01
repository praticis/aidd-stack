"""main's and head's dry-runs of each live snapshot, section by section: the records that differ by their key, then
the fields that differ on a key both keep, with the snapshot as a number, CALLS by strategy, the CALLS that do not
dispatch and those that hold receivers. No name leaves this script.
    dry_sections.py DRY_DIR"""
import collections
import json
import sys
from pathlib import Path

KEYS = {"files": ("path",), "symbols": ("id",), "calls": ("caller_id", "callee_id", "line", "strategy", "receivers"),
        "imports": ("file_id", "target_id", "spec"), "hierarchy": ("source_id", "kind", "target_id", "receivers"),
        "endpoints": ("method", "path", "file_id", "line"),
        "http_calls": ("method", "path", "file_id", "line")}
dry = Path(sys.argv[1])


def value(r: dict, k: str):
    return tuple(r.get(k) or ()) if k == "receivers" else r.get(k)


def changed(a: list, b: list, key: tuple) -> collections.Counter:
    """The fields that differ between the records of a key both sides hold as many times, each side's sorted alike."""
    groups = []
    for run in (a, b):
        g = collections.defaultdict(list)
        for r in run:
            g[tuple(value(r, k) for k in key)].append(r)
        groups.append(g)
    fields = collections.Counter()
    for k in groups[0].keys() & groups[1].keys():
        pairs = zip(*(sorted(g[k], key=lambda r: json.dumps(r, sort_keys=True)) for g in groups))
        fields.update(f for ra, rb in pairs for f in ra.keys() | rb.keys() if ra.get(f) != rb.get(f))
    return fields


for n, main in enumerate(sorted(dry.glob("*__main.json")), 1):
    a, b = json.load(open(main)), json.load(open(str(main).replace("__main.json", "__head.json")))
    out = []
    for sec, key in KEYS.items():
        ka = collections.Counter(tuple(value(r, k) for k in key) for r in a.get(sec, []))
        kb = collections.Counter(tuple(value(r, k) for k in key) for r in b.get(sec, []))
        if ka != kb:
            out.append(f"{sec} -{sum((ka - kb).values())} +{sum((kb - ka).values())}")
        fields = changed(a.get(sec, []), b.get(sec, []), key)
        if fields:
            out.append(f"{sec} changed " + ", ".join(f"{f} {c}" for f, c in fields.most_common()))
    direct = [sum(c.get("virtual") is False for c in run["calls"]) for run in (a, b)]
    if direct[0] != direct[1]:
        out.append(f"not dispatching {direct[0]} -> {direct[1]}")
    held = [sum(bool(c.get("receivers")) for c in run["calls"]) for run in (a, b)]
    if held[0] != held[1]:
        out.append(f"calls with receivers {held[0]} -> {held[1]}")
    calls = ""
    if any(o.startswith("calls -") for o in out):
        sa = collections.Counter(c["strategy"] for c in a["calls"])
        sb = collections.Counter(c["strategy"] for c in b["calls"])
        calls = " | by strategy " + ", ".join(f"{s} {sb[s] - sa[s]:+d}" for s in sorted(sa | sb) if sb[s] != sa[s])
    langs = collections.Counter(f.get("language") for f in a.get("files", []))
    print(f"snapshot {n} ({', '.join(f'{lang} {c}' for lang, c in langs.most_common(2))}): "
          + ("identical" if not out else "; ".join(out)) + calls)
