"""The graph of one tree against its references: the numbers a pull request may not lower.

   scorecard.py RUN_DIR [--rows DIR] [--scopes FILE] [--floors FILE] [--min-keyed PCT] [--write-floors]
   scorecard.py --lowered BASE_FLOORS FLOORS

RUN_DIR holds the micro dry-runs of one tree (`<repo>.json.gz`, what `micro.sh` leaves in $C/micro). For every repo it
measures `typed-share`, the percent of its CALLS that a type decided (`receiver-type*` and `inherited*`), which needs no
reference and holds for every language. With --rows DIR, a repo that has `DIR/checker-<repo>.jsonl` (what
`checks/ts_checker.js --link` prints) is also measured against TypeScript's checker, as `ts_vs_checker.py` judges one
change's edges, but over the whole tree:

  keyed            percent of the TS calls in a file the checker has rows for; under --min-keyed (50) the two sides are
                   keyed differently and nothing below means anything, so the repo fails
  typed-precision  percent of the typed edges (`receiver-type`, `inherited`) at a site the checker judges that it confirms
  recall           percent of the sites where the checker names a declaration of the repo that have an edge to it
  typed-recall     the same, by a typed edge

With --scopes FILE (what `checks/python_scopes.py --json` writes), each Python repo in it is measured against CPython's
`symtable` too: `scope-agreement`, the percent of its files that compile whose every scope and name the scope index
classifies as the compiler does (100 is the only answer: a difference is a defect of the index).

--floors FILE (`indexer/scripts/checks/reference_floors.txt`: `repo.metric :: floor :: note`, one per line, `#` a comment)
is what a number may not fall under. The scorecard ends in 1 when a number is under its floor, has no floor, has a floor
and was not measured, or is invalid; in 2 when its input is wrong. --write-floors prints the lines of the numbers it
measured, each rounded down to a hundredth, to review and commit. --lowered prints, one per line, the floors that FLOORS
holds under the ones in BASE_FLOORS (`name was is`): what a change lowers, which the gates ask the `graph-change` label for."""
from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ts_vs_checker as T  # noqa: E402

SEPARATOR = " :: "
NAME = re.compile(r"[a-z0-9][a-z0-9-]*\.[a-z-]+")
MIX_TYPED = ("receiver-type", "inherited")
AGREE = ("agrees", "agrees (via .d.ts pair)")
BY_REFERENCE = ("typed-precision", "recall", "typed-recall")


class Metric(NamedTuple):
    name: str
    value: float
    hit: int
    of: int


class Floor(NamedTuple):
    name: str
    floor: float
    note: str


def pct(n: int, whole: int) -> float:
    return 100.0 * n / whole if whole else 0.0


def rounded_down(value: float) -> float:
    return math.floor(round(value, 6) * 100) / 100


def load_floors(text: str) -> list[Floor]:
    floors: list[Floor] = []
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        parts = [p.strip() for p in raw.split(SEPARATOR, 2)]
        if len(parts) != 3 or not all(parts) or not NAME.fullmatch(parts[0]):
            raise ValueError(f"line {n}: expected `repo.metric :: floor :: note`")
        try:
            value = float(parts[1])
        except ValueError:
            raise ValueError(f"line {n}: the floor of {parts[0]} is not a number") from None
        if any(f.name == parts[0] for f in floors):
            raise ValueError(f"line {n}: {parts[0]} already has a floor")
        floors.append(Floor(parts[0], value, parts[2]))
    return floors


def mix(repo: str, run: dict) -> Metric:
    typed = sum(1 for c in run["calls"] if c["strategy"].startswith(MIX_TYPED))
    return Metric(f"{repo}.typed-share", pct(typed, len(run["calls"])), typed, len(run["calls"]))


def decided(sites: dict) -> dict:
    """The sites where the checker names a declaration of the repo, with the forms a `.d.ts` pair may take."""
    out = {}
    for key, declared in sites.items():
        names = {d for found in declared for d in found if d != "outside"}
        if names:
            out[key] = names | {T.pair(d) for d in names}
    return out


def reached(calls: list[dict]) -> dict:
    out = collections.defaultdict(set)
    for c in calls:
        out[(T.path_of(c["caller_id"]), c["line"], T.called(c))].add(T.qualified(c["callee_id"]))
    return out


def reference(repo: str, run: dict, sites: dict) -> list[Metric]:
    ts = T.in_ts(run)
    calls = [c for c in run["calls"] if ts(c)]
    typed = [c for c in calls if c["strategy"].removesuffix("-ambiguous") in T.TYPED]
    _, _, calls_in, n = T.keyed(sites, calls)
    verdicts = collections.Counter(T.verdict(c, sites) for c in typed)
    judged = sum(v for k, v in verdicts.items() if k != T.NO_SITE)
    agree = sum(verdicts[k] for k in AGREE)
    sites_decided, any_edge, typed_edge = decided(sites), reached(calls), reached(typed)
    hit = sum(1 for k, names in sites_decided.items() if any_edge.get(k, set()) & names)
    typed_hit = sum(1 for k, names in sites_decided.items() if typed_edge.get(k, set()) & names)
    return [Metric(f"{repo}.keyed", pct(calls_in, n), calls_in, n),
            Metric(f"{repo}.typed-precision", pct(agree, judged), agree, judged),
            Metric(f"{repo}.recall", pct(hit, len(sites_decided)), hit, len(sites_decided)),
            Metric(f"{repo}.typed-recall", pct(typed_hit, len(sites_decided)), typed_hit, len(sites_decided))]


def scope_metrics(counts: dict) -> list[Metric]:
    out = []
    for repo, c in sorted(counts.items()):
        compared = c.get("files compared", 0)
        agree = compared - c.get("files differing", 0)
        out.append(Metric(f"{repo}.scope-agreement", pct(agree, compared), agree, compared))
    return out


def measure(run_dir: Path, rows_dir: Path | None, scopes: Path | None = None) -> list[Metric]:
    out: list[Metric] = scope_metrics(json.loads(scopes.read_text())) if scopes else []
    for path in sorted(glob.glob(str(run_dir / "*.json.gz"))):
        repo = os.path.basename(path)[: -len(".json.gz")]
        with gzip.open(path, "rt") as handle:
            run = json.load(handle)
        out.append(mix(repo, run))
        if rows_dir and (rows_dir / f"checker-{repo}.jsonl").is_file():
            out += reference(repo, run, T.checker_sites(str(rows_dir / f"checker-{repo}.jsonl")))
    return out


def judge(metrics: list[Metric], floors: list[Floor], min_keyed: float) -> list[tuple[str, Metric | None, Floor | None]]:
    """(status, measured, floor) per name: ok, below, invalid, unfloored, not measured."""
    have = {m.name: m for m in metrics}
    keyed = {m.name.split(".")[0]: m.value for m in metrics if m.name.endswith(".keyed")}
    want = {f.name: f for f in floors}
    rows = []
    for name in sorted(set(have) | set(want)):
        m, f = have.get(name), want.get(name)
        repo = name.split(".")[0]
        if m is None:
            status = "not measured"
        elif repo in keyed and keyed[repo] < min_keyed and name.split(".")[1] in BY_REFERENCE:
            status = "invalid"
        elif f is None:
            status = "unfloored"
        else:
            status = "ok" if round(m.value, 6) >= f.floor else "below"
        rows.append((status, m, f))
    return rows


def report(rows: list[tuple[str, Metric | None, Floor | None]]) -> str:
    lines = ["### The graph against its references", "", "| Number | Value | Of | Floor | Headroom | |", "|---|---|---|---|---|---|"]
    for status, m, f in rows:
        name = (m or f).name
        value = f"{m.value:.2f} %" if m else ""
        of = f"{m.hit:,} of {m.of:,}" if m else ""
        floor = f"{f.floor:.2f} %" if f else ""
        room = f"{m.value - f.floor:+.2f}" if m and f else ""
        lines.append(f"| `{name}` | {value} | {of} | {floor} | {room} | {status} |")
    bad = [status for status, _, _ in rows if status != "ok"]
    if bad:
        lines += ["", f"{len(bad)} number(s) not ok: a floor is lowered, in the same diff and under the `graph-change` label, "
                      "by editing its line in `indexer/scripts/checks/reference_floors.txt`; a new number gets a line "
                      "(`--write-floors` prints them)."]
    return "\n".join(lines) + "\n"


def lowered(base: list[Floor], floors: list[Floor]) -> list[tuple[str, float, float]]:
    was = {f.name: f.floor for f in base}
    return [(f.name, was[f.name], f.floor) for f in floors if f.name in was and f.floor < was[f.name]]


def lowered_main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        found = lowered(load_floors(Path(argv[0]).read_text()), load_floors(Path(argv[1]).read_text()))
    except (OSError, ValueError) as error:
        print(f"scorecard.py: {error}", file=sys.stderr)
        return 2
    print("\n".join(f"{name} {was} {now}" for name, was, now in found))
    return 0


def main(argv: list[str]) -> int:
    return lowered_main(argv[1:]) if argv[:1] == ["--lowered"] else run(argv)


def run(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="scorecard.py", add_help=False, usage=(
        "scorecard.py RUN_DIR [--rows DIR] [--scopes FILE] [--floors FILE] [--min-keyed PCT] [--write-floors]"))
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--rows", type=Path)
    ap.add_argument("--scopes", type=Path)
    ap.add_argument("--floors", type=Path)
    ap.add_argument("--min-keyed", type=float, default=50.0)
    ap.add_argument("--write-floors", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exit_:
        print(__doc__, file=sys.stderr)
        return exit_.code
    try:
        floors = load_floors(args.floors.read_text()) if args.floors else []
        metrics = measure(args.run_dir, args.rows, args.scopes)
    except (OSError, ValueError) as error:
        print(f"scorecard.py: {error}", file=sys.stderr)
        return 2
    if args.write_floors:
        print("\n".join(f"{m.name}{SEPARATOR}{rounded_down(m.value)}{SEPARATOR}measured on the base" for m in metrics))
        return 0
    rows = judge(metrics, floors, args.min_keyed)
    print(report(rows), end="")
    return 1 if any(status != "ok" for status, _, _ in rows) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
