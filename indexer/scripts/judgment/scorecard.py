"""The graph of one tree against its references: the counts a pull request may not move the wrong way.

   scorecard.py RUN_DIR [--base DIR] [--rows DIR] [--scopes FILE] [--floors FILE] [--min-keyed PCT] [--write-floors]
   scorecard.py --lowered BASE_FLOORS FLOORS

RUN_DIR holds the micro dry-runs of one tree (`<repo>.json.gz`, what `micro.sh` leaves in $C/micro). A repo that has
`DIR/checker-<repo>.jsonl` in --rows (what `checks/ts_checker.js --link` prints) is measured against TypeScript's checker, as
`ts_vs_checker.py` judges one change's edges, but over the whole tree (`scorecard_measure.py` says how an edge is classed).

Gated, by strategy (`receiver-type`, `inherited`) of each such repo: the typed edges the checker `confirmed` (a floor: they may
not fall) and the ones it `contradicted` (a ceiling: they may not rise). A count has no denominator, so a call form the graph
learns to read, which adds by-name edges, moves none of them. The bounds are in --floors (`indexer/scripts/checks/reference_floors.txt`,
`repo.strategy.confirmed :: >= N :: note`, `repo.strategy.contradicted :: <= N :: note`, `#` a comment), and the graph is
deterministic, so a count past its bound is a change of the graph, never noise.

--scopes FILE (`checks/python_scopes.py --json`) adds the Python repos, measured against CPython's symbol table as `repo.scopes.confirmed`
(files whose every scope and name the index classifies as the table does) and `repo.scopes.contradicted` (files where one differs),
bounded as the others are: it depends on the tree's code and the clone, not on the dry-runs.

With --base DIR (the dry-runs of the tree it is compared to) it also lists the sites where the base has a confirmed typed edge and
RUN_DIR has none, a win lost, and prints the numbers that have no bound (the typed share of every repo, recall, the by-name edges
the checker contradicts, the typed edges it does not decide) as the base, the tree and the change.

It ends in 0 when every count holds, in 1 when one is past its bound, has no bound, has a bound and was not measured, or is
invalid (a repo's calls are under --min-keyed percent in files the checker has rows for, 50 by default: the two sides are keyed
differently and nothing below means anything), in 3 when only wins were lost, and in 2 when its input is wrong. --write-floors
prints the lines of the counts it measured, to review and commit. --lowered prints, one per line, the bounds a change lowers
(a floor that falls, a ceiling that rises, a line that goes) between the base's list and its own; it ends in 0."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scorecard_measure as M  # noqa: E402

SEPARATOR = " :: "
NAME = re.compile(r"[a-z0-9][a-z0-9-]*\.[a-z-]+\.(confirmed|contradicted)")
LIMIT = re.compile(r"(>=|<=) (\d+)")
SIDE = {"confirmed": ">=", "contradicted": "<="}
LISTED = 50


class Bound(NamedTuple):
    name: str
    op: str
    limit: int
    note: str


class Row(NamedTuple):
    status: str
    name: str
    value: int | None
    bound: Bound | None


def parse_line(n: int, raw: str) -> Bound:
    parts = [p.strip() for p in raw.split(SEPARATOR, 2)]
    if len(parts) != 3 or not all(parts) or not NAME.fullmatch(parts[0]):
        raise ValueError(f"line {n}: expected `repo.strategy.confirmed :: >= N :: note` or `repo.strategy.contradicted :: <= N :: note`")
    side = SIDE[parts[0].rsplit(".", 1)[1]]
    found = LIMIT.fullmatch(parts[1])
    if not found or found.group(1) != side:
        raise ValueError(f"line {n}: {parts[0]} takes `{side} N`, a whole number")
    return Bound(parts[0], side, int(found.group(2)), parts[2])


def load_floors(text: str) -> list[Bound]:
    bounds: list[Bound] = []
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        bound = parse_line(n, raw)
        if any(b.name == bound.name for b in bounds):
            raise ValueError(f"line {n}: {bound.name} already has a bound")
        bounds.append(bound)
    return bounds


def lowered(base: list[Bound], head: list[Bound]) -> list[str]:
    """The bounds of the base that the head lowers: a floor that falls, a ceiling that rises, and a bound that is gone."""
    now = {b.name: b for b in head}
    out = []
    for b in base:
        h = now.get(b.name)
        if h is None:
            out.append(f"{b.name}: {b.op} {b.limit}, deleted")
        elif (h.limit < b.limit) if b.op == ">=" else (h.limit > b.limit):
            out.append(f"{b.name}: {b.op} {b.limit}, now {h.op} {h.limit}")
    return out


def status(name: str, n: int | None, bound: Bound | None, keyed: dict[str, float], min_keyed: float) -> str:
    if n is None:
        return "not measured"
    if keyed.get(name.split(".")[0], 100.0) < min_keyed:
        return "invalid"
    if bound is None:
        return "unbound"
    holds = n >= bound.limit if bound.op == ">=" else n <= bound.limit
    if holds:
        return "ok"
    return "below" if bound.op == ">=" else "above"


def judge(counts: dict[str, int], bounds: list[Bound], keyed: dict[str, float], min_keyed: float) -> list[Row]:
    """(status, name, count, bound) per name: ok, below a floor, above a ceiling, unbound, not measured, invalid."""
    want = {b.name: b for b in bounds}
    return [Row(status(name, counts.get(name), want.get(name), keyed, min_keyed), name, counts.get(name), want.get(name))
            for name in sorted(set(counts) | set(want))]


def room(row: Row) -> str:
    if row.value is None or row.bound is None:
        return ""
    return f"{row.value - row.bound.limit:+d}" if row.bound.op == ">=" else f"{row.bound.limit - row.value:+d}"


def gated_table(rows: list[Row]) -> list[str]:
    lines = ["| Count | Value | Bound | Room | |", "|---|---|---|---|---|"]
    for row in rows:
        value = f"{row.value:,}" if row.value is not None else ""
        bound = f"{row.bound.op} {row.bound.limit:,}" if row.bound else ""
        lines.append(f"| `{row.name}` | {value} | {bound} | {room(row)} | {row.status} |")
    bad = [row for row in rows if row.status != "ok"]
    if bad:
        lines += ["", f"{len(bad)} count(s) not ok: a bound is changed, in the same diff and under the `graph-change` label, by editing "
                      "its line in `indexer/scripts/checks/reference_floors.txt`; a new count gets a line (`--write-floors` prints them)."]
    return lines


def shown(m: M.Metric | None) -> str:
    if m is None:
        return ""
    return f"{m.value:,.0f}" if m.of == 0 else f"{m.value:.2f} % ({m.hit:,} of {m.of:,})"


def change(a: M.Metric | None, b: M.Metric | None) -> str:
    if a is None or b is None:
        return ""
    return f"{int(b.value - a.value):+,d}" if b.of == 0 else f"{b.value - a.value:+.2f}"


def numbers_table(head: dict[str, M.Metric], base: dict[str, M.Metric] | None) -> list[str]:
    if base is None:
        lines = ["| Number | Value |", "|---|---|"]
        return lines + [f"| `{name}` | {shown(m)} |" for name, m in head.items()]
    lines = ["| Number | Base | Tree | Change |", "|---|---|---|---|"]
    for name in sorted(set(head) | set(base)):
        a, b = base.get(name), head.get(name)
        lines.append(f"| `{name}` | {shown(a)} | {shown(b)} | {change(a, b)} |")
    return lines


def lost_lines(lost: dict[str, list]) -> list[str]:
    lines = []
    for repo, sites in lost.items():
        lines.append(f"{repo}: {len(sites)} site(s) where the base has a confirmed typed edge and the tree has none"
                     + (f" (the first {LISTED}):" if len(sites) > LISTED else ":"))
        lines += [f"- `{path}:{line}` `{method}`" for path, line, method in sites[:LISTED]]
    return lines


def report(rows: list[Row], head: dict[str, M.Metric], base: dict[str, M.Metric] | None, lost: dict[str, list],
           keyed: dict[str, float]) -> str:
    out = ["### The graph against its references", ""] + gated_table(rows)
    if keyed:
        out += ["", "The checker has rows for " + ", ".join(f"{pct:.1f} % of {repo}'s TS calls" for repo, pct in sorted(keyed.items())) + "."]
    if base is not None:
        out += ["", "### Wins lost", ""] + (lost_lines(lost) if lost else ["None: every site the base confirms, the tree confirms."])
    return "\n".join(out + ["", "### Not gated", ""] + numbers_table(head, base)) + "\n"


def code(rows: list[Row], lost: dict[str, list]) -> int:
    if any(row.status != "ok" for row in rows):
        return 1
    return 3 if lost else 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="scorecard.py", add_help=False, usage=(
        "scorecard.py RUN_DIR [--base DIR] [--rows DIR] [--scopes FILE] [--floors FILE] [--min-keyed PCT] [--write-floors]"))
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--base", type=Path)
    ap.add_argument("--rows", type=Path)
    ap.add_argument("--scopes", type=Path)
    ap.add_argument("--floors", type=Path)
    ap.add_argument("--min-keyed", type=float, default=50.0)
    ap.add_argument("--write-floors", action="store_true")
    return ap


def print_lowered(files: list[str]) -> int:
    try:
        if len(files) != 2:
            raise ValueError("--lowered takes the base's list and the change's")
        print("\n".join(lowered(load_floors(Path(files[0]).read_text()), load_floors(Path(files[1]).read_text()))))
    except (OSError, ValueError) as error:
        print(f"scorecard.py: {error}", file=sys.stderr)
        return 2
    return 0


def run(args: argparse.Namespace) -> int:
    bounds = load_floors(args.floors.read_text()) if args.floors else []
    head = M.measure(args.run_dir, args.rows)
    base = M.measure(args.base, args.rows) if args.base else None
    counts = {**M.gated(head), **(M.scopes(args.scopes) if args.scopes else {})}
    if args.write_floors:
        print("\n".join(f"{n} :: {SIDE[n.rsplit('.', 1)[1]]} {v} :: measured on the base" for n, v in counts.items()))
        return 0
    rows = judge(counts, bounds, M.keyed_of(head), args.min_keyed)
    lost = M.lost_wins(base, head) if base is not None else {}
    print(report(rows, M.numbers(head), M.numbers(base) if base is not None else None, lost, M.keyed_of(head)), end="")
    return code(rows, lost)


def main(argv: list[str]) -> int:
    if argv[:1] == ["--lowered"]:
        return print_lowered(argv[1:])
    try:
        args = parser().parse_args(argv)
    except SystemExit as exit_:
        print(__doc__, file=sys.stderr)
        return exit_.code
    try:
        return run(args)
    except (OSError, ValueError) as error:
        print(f"scorecard.py: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
