#!/usr/bin/env python3
"""The micro graph's regression check: full dry-runs (`aidd index --dry-run --out`) of a fixed set of public
repositories by two versions of the indexer, compared record by record. The HTTP corpus does not run the resolver, so
a change to the files, symbols, `CALLS`, `IMPORTS` or violations shows only here.

    python scripts/micro.py --dir ~/.cache/aidd-corpus/repos --prepare [repo ...]   # clone the pins, largest first
    python scripts/micro.py --compare BASE_DIR HEAD_DIR [--show N] [repo ...]       # the report

`micro.sh` runs the dry-runs in between, one container each, and keeps them as `<repo>.json.gz`. With no repo named,
the whole set. `--compare` exits 1 when a repository differs or was not compared.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import http_corpus as H  # noqa: E402

# Each language's resolver on a small and a large repository. Grafana is there for scale: a lookup that grows with the
# repo per call shows on its million call sites first.
MICRO = ("eshop", "jellyfin", "btcpayserver", "umbraco",
         "vikunja", "gitea", "mattermost", "grafana",
         "dispatch", "netbox",
         "ghost", "outline")
# Out of the HTTP corpus, which keeps every tree in memory; a dry-run fits in 5 GB.
EXTRA_PINS = {"grafana": ("grafana/grafana", "044dd4f9457cb43fcecc30ec61f376cbff637d57")}
PINS = {**H.CORPUS, **EXTRA_PINS}
# the run's own metadata, not the graph
SKIP = frozenset({"repo", "counts"})
WIDTH = 500


def load(d: Path, name: str) -> dict | None:
    f = d / f"{name}.json.gz"
    if not f.exists():
        return None
    with gzip.open(f, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def records(payload: dict) -> dict[str, Counter]:
    """Each list of a dry-run as a multiset of whole records: a field that changes anywhere shows, and so does a
    record that appears once more."""
    return {k: Counter(json.dumps(x, sort_keys=True, default=str) for x in v)
            for k, v in payload.items() if k not in SKIP and isinstance(v, list)}


def diff(base: dict, head: dict) -> dict[str, tuple[Counter, Counter]]:
    """The lists that differ: (records gone, records new) for each."""
    a, b = records(base), records(head)
    out = {}
    for k in sorted(set(a) | set(b)):
        x, y = a.get(k, Counter()), b.get(k, Counter())
        if x != y:
            out[k] = (x - y, y - x)
    return out


def _print_diff(d: dict[str, tuple[Counter, Counter]], show: int) -> None:
    for k, (gone, new) in d.items():
        print(f"  {k}: -{sum(gone.values())} +{sum(new.values())}")
        for sign, c in (("-", gone), ("+", new)):
            for r in sorted(c)[:show]:
                print(f"    {sign} {r[:WIDTH]}")


def report_repo(name: str, base: Path, head: Path, show: int) -> bool | None:
    """Prints one repository's comparison: True when it differs, None when a dry-run is missing."""
    a, b = load(base, name), load(head, name)
    if a is None or b is None:
        missing = [side for side, run in (("base", a), ("head", b)) if run is None]
        print(f"{name}: no {' or '.join(missing)} dry-run")
        return None
    d = diff(a, b)
    sizes = " ".join(f"{k}={len(a.get(k, []))}" for k in ("files", "symbols", "calls", "imports"))
    print(f"{name}: {'DIFFERS' if d else 'identical'} ({sizes})")
    _print_diff(d, show)
    return bool(d)


def compare(base: Path, head: Path, names: list[str], show: int) -> int:
    results = {n: report_repo(n, base, head, show) for n in names}
    differ = [n for n, r in results.items() if r]
    missing = [n for n, r in results.items() if r is None]
    print(f"\n{len(differ)} repo(s) differ" + (f": {', '.join(differ)}" if differ else ""))
    if missing:
        print(f"not compared: {', '.join(missing)}", file=sys.stderr)
    return 1 if differ or missing else 0


def prepare(base: Path, names: list[str]) -> int:
    base.mkdir(parents=True, exist_ok=True)
    for n in names:
        H.checkout(base / n, *PINS[n])
    return H.list_repos(names, PINS, base)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.environ.get("AIDD_CORPUS_DIR", str(Path.home() / ".cache/aidd-corpus/repos")))
    ap.add_argument("--prepare", action="store_true",
                    help="clone the pinned commits that are missing, then print the repositories, the largest first")
    ap.add_argument("--compare", nargs=2, type=Path, metavar=("BASE", "HEAD"), help="two directories of dry-runs")
    ap.add_argument("--show", type=int, default=5, help="records listed per side of each list that differs")
    ap.add_argument("repos", nargs="*")
    args = ap.parse_args()
    names = args.repos or list(MICRO)
    unknown = [n for n in names if n not in PINS]
    if unknown:
        print(f"not pinned: {', '.join(unknown)}", file=sys.stderr)
        return 2
    if args.compare:
        return compare(*args.compare, names, args.show)
    if args.prepare:
        return prepare(Path(args.dir), names)
    ap.error("--prepare or --compare")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
