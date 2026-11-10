#!/usr/bin/env python3
"""The bot of the floors: what the graph holds on main, written into the bounds it beats. Plain code, no model: it reads the counts
the scorecard measured on main's own dry-runs (`checks/reference.sh --out DIR` leaves them in DIR/measured.txt) and the bounds in
`checks/reference_floors.txt`, and moves a bound only toward what is held: a floor up to the count, a ceiling down to it.

    floors_bot.py raise FLOORS MEASURED [--note TEXT] [--write]
    floors_bot.py only-raises BASE_FLOORS FLOORS
    floors_bot.py body FLOORS_BEFORE FLOORS_AFTER [--sha SHA]

`raise` prints, one per line, the bounds it moves (`name: >= 8171, now >= 8200`), and with --write sets them in FLOORS, keeping the
comments and the order; --note replaces the note of a bound it moves. It writes to stderr what main does not hold: a count below a
floor or above a ceiling, a bound whose count was not measured, a count with no bound (a person adds that line); then it ends in 1,
having moved what it could. `only-raises` prints what a change to the bounds does that a raise does not (a bound lowered, deleted or
added) and ends in 1 when there is any: a pull request that changes only the bounds is not judged by the gates. `body` prints the
body of the pull request that carries a raise, as the template of the project has it. 2: the input is wrong."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "judgment"))
import scorecard as S  # noqa: E402


def beats(bound: S.Bound, count: int) -> bool:
    """The count is past the bound on the good side: a floor it exceeds, a ceiling it undercuts."""
    return count > bound.limit if bound.op == ">=" else count < bound.limit


def breaks(bound: S.Bound, count: int) -> bool:
    return count < bound.limit if bound.op == ">=" else count > bound.limit


def counts_of(text: str) -> dict[str, int]:
    """The measured counts, from the lines `scorecard.py --write-floors` prints."""
    return {b.name: b.limit for b in S.load_floors(text)}


def alarms(bounds: list[S.Bound], counts: dict[str, int]) -> list[str]:
    """What the measure says is wrong: a bound that is broken, one with no count, a count with no bound."""
    out = []
    for b in bounds:
        count = counts.get(b.name)
        if count is None:
            out.append(f"{b.name}: {b.op} {b.limit}, not measured")
        elif breaks(b, count):
            out.append(f"{b.name}: {b.op} {b.limit}, measured {count}")
    named = {b.name for b in bounds}
    return out + [f"{name}: measured {count}, no bound" for name, count in counts.items() if name not in named]


def raised(text: str, counts: dict[str, int], note: str | None = None) -> tuple[str, list[str]]:
    """The text of the bounds with each one the measure beats set to it, and a line for each one moved."""
    out, moved = [], []
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            out.append(raw)
            continue
        bound = S.parse_line(n, raw)
        count = counts.get(bound.name)
        if count is not None and beats(bound, count):
            out.append(f"{bound.name} :: {bound.op} {count} :: {note or bound.note}")
            moved.append(f"{bound.name}: {bound.op} {bound.limit}, now {bound.op} {count}")
        else:
            out.append(raw)
    return "\n".join(out) + "\n", moved


def only_raises(base: list[S.Bound], head: list[S.Bound]) -> list[str]:
    """What a change of the bounds does that a raise does not: a bound lowered or deleted, and one added."""
    known = {b.name for b in base}
    return S.lowered(base, head) + [f"{b.name}: {b.op} {b.limit}, added" for b in head if b.name not in known]


def body(before: list[S.Bound], after: list[S.Bound], sha: str | None) -> str:
    was = {b.name: b for b in before}
    rows = [f"| `{b.name}` | {b.op} {was[b.name].limit:,} | {b.op} {b.limit:,} |" for b in after if b.name in was and b.limit != was[b.name].limit]
    where = f" on main at {sha[:7]}" if sha else " on main"
    return "\n".join([
        "Kind: chore(scripts)",
        f"Records: H5-D56; the bounds the graph holds{where}, raised; no decision and no debt",
        "Labels: none",
        "Gates: `debts` is the check that runs on a pull request that only changes `reference_floors.txt`: it fails a bound lowered, deleted or added",
        "Author decides: nothing open; merge it when the counts below are the ones you expect",
        "",
        "## What and why",
        f"The graph{where} beats {len(rows)} bound(s) of `indexer/scripts/checks/reference_floors.txt`: a floor goes up to the count held and a "
        "ceiling goes down to it, so that a later change that loses the gain fails its own pull request. Written by "
        "`indexer/scripts/floors_bot.py`, a script and not a model: it moves no bound the scorecard's count does not beat.",
        "",
        "| Count | Was | Now |", "|---|---|---|", *rows,
        "",
        "## Contracts, boundaries and proof",
        "- **Contract:** `reference_floors.txt` (H5-D53, H5-D56): a count past its bound fails a pull request, so a bound is only raised here, "
        "and lowered by a change of the graph under `graph-change`.",
        "- **Boundary:** the scorecard measures; the bot writes what it measured into the lines that exist.",
        f"- **Reference:** the scorecard of main's own dry-runs{where}: the counts above are its.",
        "- **Unknown:** nothing.",
        "",
        "## Measures",
        "The `floors` job measured the counts on main; the `debts` check of this pull request holds that no bound is lowered, deleted or added.",
        "",
        "## Left out on purpose",
        "A count with no bound gets no line (a person adds it with `scorecard.py --write-floors`); a bound that main does not hold is an "
        "alarm of the job, not a change.",
        "",
        "Live validation: not needed: scripts and CI; no graph or indexer change",
        ""])


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="floors_bot.py", add_help=False)
    sub = ap.add_subparsers(dest="mode", required=True)
    r = sub.add_parser("raise")
    r.add_argument("floors", type=Path)
    r.add_argument("measured", type=Path)
    r.add_argument("--note")
    r.add_argument("--write", action="store_true")
    o = sub.add_parser("only-raises")
    o.add_argument("base", type=Path)
    o.add_argument("floors", type=Path)
    b = sub.add_parser("body")
    b.add_argument("before", type=Path)
    b.add_argument("after", type=Path)
    b.add_argument("--sha")
    return ap


def show(lines: list[str], stream) -> None:
    if lines:
        print("\n".join(lines), file=stream)


def run(args: argparse.Namespace) -> int:
    if args.mode == "only-raises":
        found = only_raises(S.load_floors(args.base.read_text()), S.load_floors(args.floors.read_text()))
        show(found, sys.stdout)
        return 1 if found else 0
    if args.mode == "body":
        print(body(S.load_floors(args.before.read_text()), S.load_floors(args.after.read_text()), args.sha), end="")
        return 0
    text, counts = args.floors.read_text(), counts_of(args.measured.read_text())
    new, moved = raised(text, counts, args.note)
    if args.write and moved:
        args.floors.write_text(new)
    show(moved, sys.stdout)
    wrong = alarms(S.load_floors(text), counts)
    show(wrong, sys.stderr)
    return 1 if wrong else 0


def main(argv: list[str]) -> int:
    try:
        args = parser().parse_args(argv)
    except SystemExit as exit_:
        print(__doc__, file=sys.stderr)
        return 2 if exit_.code else 0
    try:
        return run(args)
    except (OSError, ValueError) as error:
        print(f"floors_bot.py: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
