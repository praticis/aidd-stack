#!/usr/bin/env python3
"""The register of technical debts (docs/tech-debt.md) against its cases and the roadmap, as CI runs it:

- each case a debt names is a case of the debts' tests (indexer/tests/test_*_debts.py), and each case there is named
  by a debt; each of those files marks its cases as strict xfails. An open debt with no case says so, in a Case cell that
  starts with `none yet`, and is counted in the summary; one that says it and names a case is wrong. A closed debt's
  xfail is gone, so the case it names is no longer one of them;
- a debt's due is `F1.2`, a `fix(<scope>)` PR before F1.2 (`fix(csharp)`, `fix(go)`, ...), a step of H5 (`H5 step 6`),
  or `closed`, and no document names a debt the register lacks;
- an item of the roadmap (docs/ROADMAP.md, docs/roadmap/*.md) is not ticked while a debt due in it is open: F1.2 for
  the debts due in F1.2 and in the `fix` PRs before it, and F1.17 for those due in a step of H5;
- with --base-register, the open debts whose Due cell changed against that register are listed, each with a warning on
  stderr for the pull request's checks. A move is not a finding.

Prints Markdown for the job summary; exits 1 when it finds anything. It reads files only: no Docker, no network.

    python3 -I indexer/scripts/debts.py [--root DIR] [--base-register FILE]
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE_ID = re.compile(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`")
DEBT = re.compile(r"TD-(\d+)(?: to TD-(\d+))?")
NO_CASE = "none yet"
FIX = re.compile(r"`(fix\([a-z]+\))`")
F12 = re.compile(r"F1\.2(?!\d)")
ITEM = re.compile(r"^\s*- \[([ xX])\] (?:\*\*)?([A-Z]{1,2}\d+(?:\.\d+)*)\b", re.MULTILINE)


def register(text: str) -> tuple[list[dict], list[str]]:
    """The register's rows, and what is wrong with their shape."""
    rows, found = [], []
    for line in text.splitlines():
        if not line.startswith("| TD-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if len(cells) != 5:
            found.append(f"{cells[0]}: a row has {len(cells)} columns, not 5")
            continue
        rows.append({"id": cells[0], "due": cells[3], "cases": CASE_ID.findall(cells[4]),
                     "pending": cells[4].lower().startswith(NO_CASE)})
    ids = [r["id"] for r in rows]
    found += [f"{i}: listed twice" for i in sorted(set(ids)) if ids.count(i) > 1]
    return rows, found


def phase(due: str) -> str:
    if due.lower().startswith("closed"):
        return "closed"
    if F12.match(due):
        return "F1.2"
    if due.startswith("H5 step"):
        return "H5"
    fix = FIX.search(due)
    return fix.group(1) if fix else "?"


def locked_item(due: str) -> str | None:
    """The roadmap item an open debt keeps from being ticked: by its phase, never by the wording of its due."""
    name = phase(due)
    if name == "F1.2" or name.startswith("fix("):
        return "F1.2"
    if name == "H5":
        return "F1.17"
    return None


def case_ids(text: str) -> list[str]:
    """The ids a test module gives to `case("id", ...)`."""
    calls = [n for n in ast.walk(ast.parse(text))
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "case" and n.args]
    return [c.args[0].value for c in calls if isinstance(c.args[0], ast.Constant) and isinstance(c.args[0].value, str)]


def debt_cases(tests: Path) -> tuple[dict[str, str], list[str]]:
    """Each case of the debts' tests with its file, and the files that do not mark their cases strict."""
    cases, found = {}, []
    for path in sorted(tests.glob("test_*_debts.py")):
        text = path.read_text()
        if "strict=True" not in text:
            found.append(f"{path.name}: its cases are not strict xfails")
        for cid in case_ids(text):
            if cid in cases:
                found.append(f"{cid}: a case of two tests")
            cases[cid] = path.name
    return cases, found


def listed(segment: str) -> set[str]:
    """The debts a text names, a range `TD-001 to TD-004` included."""
    ids: set[str] = set()
    for first, last in DEBT.findall(segment):
        ids |= {f"TD-{n:03d}" for n in range(int(first), int(last or first) + 1)}
    return ids


def roadmap_items(root: Path) -> dict[str, list[tuple[str, bool]]]:
    """Each item of the roadmap, with the file that holds it and whether it is ticked there."""
    files = [root / "docs" / "ROADMAP.md", *sorted((root / "docs" / "roadmap").glob("*.md"))]
    items: dict[str, list[tuple[str, bool]]] = {}
    for path in files:
        if path.is_file():
            for box, item in ITEM.findall(path.read_text()):
                items.setdefault(item, []).append((str(path.relative_to(root)), box != " "))
    return items


def check_cases(rows: list[dict], cases: dict[str, str]) -> list[str]:
    named = {c for r in rows for c in r["cases"]}
    found = [f"{r['id']}: names `{c}`, which no debts' test has" for r in rows for c in r["cases"] if c not in cases]
    found += [f"`{c}` ({f}) is named by no debt" for c, f in sorted(cases.items()) if c not in named]
    found += [f"{r['id']}: names no case" for r in rows
              if not r["cases"] and not r["pending"] and phase(r["due"]) != "closed"]
    found += [f"{r['id']}: says there is no case yet and names one" for r in rows if r["pending"] and r["cases"]]
    found += [f"{r['id']}: is closed, and its case `{c}` is still a strict xfail of {cases[c]}" for r in rows
              if phase(r["due"]) == "closed" for c in r["cases"] if c in cases]
    return found


def check_dues(rows: list[dict]) -> list[str]:
    return [f"{r['id']}: a due the check does not know ({r['due']!r}): F1.2, a `fix(<scope>)` PR, an H5 step, or closed"
            for r in rows if phase(r["due"]) == "?"]


def check_locks(rows: list[dict], items: dict[str, list[tuple[str, bool]]]) -> list[str]:
    """An item ticked while a debt due in it is open, and an item the register's dues name that the roadmap lacks."""
    locked: dict[str, list[str]] = {}
    for r in rows:
        item = locked_item(r["due"])
        if item:
            locked.setdefault(item, []).append(r["id"])
    found = []
    for item, ids in sorted(locked.items()):
        where = items.get(item)
        if not where:
            found.append(f"the roadmap has no item {item}, where {len(ids)} open debts are due")
            continue
        found += [f"{item} is ticked in {doc}, and {', '.join(sorted(ids))} are open and due in it"
                  for doc, ticked in where if ticked]
    return found


def check_docs(rows: list[dict], docs: dict[str, str]) -> list[str]:
    known = {r["id"] for r in rows}
    return [f"{doc} names {i}, which the register lacks"
            for doc, body in sorted(docs.items()) for i in sorted(listed(body) - known)]


def check(root: Path) -> tuple[list[str], str]:
    rows, found = register((root / "docs" / "tech-debt.md").read_text())
    cases, more = debt_cases(root / "indexer" / "tests")
    docs = {str(p.relative_to(root)): p.read_text() for p in sorted((root / "docs").rglob("*.md"))
            if p.name != "tech-debt.md"}
    found += more + check_cases(rows, cases) + check_dues(rows) + check_locks(rows, roadmap_items(root))
    found += check_docs(rows, docs)
    closed = sum(phase(r["due"]) == "closed" for r in rows)
    pending = sum(r["pending"] and phase(r["due"]) != "closed" for r in rows)
    later = f"; {pending} open with no case yet" if pending else ""
    counts = f"{len(rows)} debts ({len(rows) - closed} open, {closed} closed)"
    return found, f"{counts}; {len(cases)} cases in the debts' tests{later}"


def moved(base: list[dict], rows: list[dict]) -> list[str]:
    """The open debts whose Due cell changed against the base, its wording included; a debt new to the register, one
    that closed and one that reopened did not move."""
    before = {r["id"]: r["due"] for r in base}
    lines = []
    for r in rows:
        old = before.get(r["id"])
        if old is None or old == r["due"] or "closed" in (phase(old), phase(r["due"])):
            continue
        shift = "" if phase(old) == phase(r["due"]) else f" (phase: {phase(old)} → {phase(r['due'])})"
        lines.append(f'{r["id"]}: "{old}" → "{r["due"]}"{shift}')
    return lines


def report_moves(lines: list[str], compared: bool) -> None:
    """The moves in the summary, and one warning each on stderr, where the runner reads it and the summary does not."""
    if not compared:
        print("\nThe base register is empty or missing: no due was compared.")
        return
    print("\nDue moved against the base:" if lines else "\nNo open debt's due moved against the base.")
    for line in lines:
        print(f"- {line}")
        print(f"::warning title=A debt's due moved::{line}", file=sys.stderr)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--base-register", type=Path, help="the register at the base, for the debts whose due moved")
    args = ap.parse_args(argv)
    found, summary = check(args.root)
    print("### Technical debts\n")
    print(summary + ("" if not found else f"; {len(found)} finding(s):\n"))
    for line in found:
        print(f"- {line}")
    lines = None
    if args.base_register is not None:
        tree = register((args.root / "docs" / "tech-debt.md").read_text())[0]
        base = register(args.base_register.read_text())[0]
        lines = moved(base, tree)
        report_moves(lines, bool(base))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
