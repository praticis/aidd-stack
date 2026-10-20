"""H6 step 1: from the replay's records, what each cache policy re-runs between consecutive commits, whether its key
ever missed a change (a hit whose scan differs), and the time a warm run would take, from the per-file times.

    python3 evaluate.py OUT_DIR [OUT_DIR ...]
"""

from __future__ import annotations

import gzip
import json
import statistics
import sys
from pathlib import Path

POLICIES = ("B: every scan", "file only (A's floor)", "D: whole repo", "D: per package, raw", "D: per package",
            "C: entries read")


def load(d: Path) -> list[dict]:
    return [json.load(gzip.open(p, "rt")) for p in sorted(d.glob("*.json.gz"))]


def rerun(policy: str, path: str, a: dict, b: dict) -> bool | None:
    fa, fb = a["files"].get(path), b["files"][path]
    if fa is None or "scan" not in fa or fa["key"] != fb["key"]:
        return True
    if policy == "B: every scan":
        return True
    if policy == "file only (A's floor)":
        return False
    if policy == "D: whole repo":
        return a["structure"] != b["structure"] or sorted(a["proj"].items()) != sorted(b["proj"].items())
    if any(r not in b["sv"] for r in fa["views"]):
        return None
    if any(a["sv"][r] != b["sv"][r] for r in fa["views"]):
        return True
    dg = "raw" if policy.endswith("raw") else "proj"
    own = path.rsplit("/", 1)[0] if "/" in path else "."
    if policy.startswith("D: per package"):
        dirs = set(fa["dirs"]) | {own}
        if any(a[dg].get(d) != b[dg].get(d) for d in dirs):
            return True
        return any(a["classes"].get(n) != b["classes"].get(n) for n in fa["classes"])
    if any(r not in b["cv"] for r in fa["c"]):
        return None
    return any(a["cv"][r] != b["cv"][r] for r in fa["c"])


def pair(a: dict, b: dict) -> dict:
    changed = [p for p, f in b["files"].items() if a["files"].get(p, {}).get("key") != f["key"]]
    map1_bad = [p for p, f in b["files"].items() if p not in changed and a["files"][p]["sum"] != f["sum"]]
    fixed = sum(b["times"][k] for k in ("discover", "reduce", "digests", "compose", "resolve"))
    t1 = sum(b["files"][p]["t1"] for p in changed)
    scanned = [p for p, f in b["files"].items() if "scan" in f]
    out = {"changed": len(changed), "map1_bad": map1_bad, "fixed": fixed, "t1": t1, "policies": {}}
    for pol in POLICIES:
        runs, missed, unknown, t2 = 0, [], 0, 0.0
        for p in scanned:
            r = rerun(pol, p, a, b)
            if r is None:
                unknown += 1
                r = True
            if r:
                runs += 1
                t2 += b["files"][p]["t2"]
            elif a["files"][p]["scan"] != b["files"][p]["scan"]:
                missed.append(p)
        out["policies"][pol] = {"runs": runs, "missed": missed, "unknown": unknown, "t2": t2}
    return out


def q(xs: list, f: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(f * len(xs)))] if xs else 0


def report(d: Path) -> None:
    runs = load(d)
    pairs = [pair(a, b) for a, b in zip(runs, runs[1:])]
    print(f"\n## {d.name}: {len(runs)} commits, {len(pairs)} pushes; scanned files {runs[-1]['scanned']}, "
          f"parsed {len(runs[-1]['files'])}")
    ch = [p["changed"] for p in pairs]
    print(f"parsed files changed per push: median {statistics.median(ch)}, p90 {q(ch, .9)}, max {max(ch)}")
    print(f"map 1 keys that hit with a different summary: {sum(len(p['map1_bad']) for p in pairs)}")
    cold = statistics.median(r["times"]["map1"] + r["times"]["map2_tracked"] + sum(
        r["times"][k] for k in ("discover", "reduce", "digests", "compose", "resolve")) for r in runs)
    print(f"fixed part of a warm run (discover, reduce, digests, compose, resolve): median "
          f"{statistics.median(p['fixed'] for p in pairs):.1f}s; map 1 of the changed files, CPU: median "
          f"{statistics.median(p['t1'] for p in pairs):.2f}s")
    print(f"\n| Policy | Scans re-run per push, median / p90 / max | Keys that missed a change | Map 2 CPU per push, "
          f"median / p90 (s) |\n|---|---|---|---|")
    for pol in POLICIES:
        r = [p["policies"][pol]["runs"] for p in pairs]
        t = [p["policies"][pol]["t2"] for p in pairs]
        missed = sum(len(p["policies"][pol]["missed"]) for p in pairs)
        unk = sum(p["policies"][pol]["unknown"] for p in pairs)
        print(f"| {pol} | {statistics.median(r):.0f} / {q(r, .9)} / {max(r)} | {missed}"
              + (f" ({unk} unknown)" if unk else "") + f" | {statistics.median(t):.1f} / {q(t, .9):.1f} |")
    for pol in POLICIES:
        for p, b in zip(pairs, runs[1:]):
            for path in p["policies"][pol]["missed"][:3]:
                print(f"  missed by {pol}: {b['k']:02d} {path}")
    print(f"(cold, tracked, workers=4: median {cold:.1f}s)")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        report(Path(arg))
