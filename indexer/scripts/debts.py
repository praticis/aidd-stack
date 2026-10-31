#!/usr/bin/env python3
"""The register of technical debts (docs/tech-debt.md) against its cases and the ROADMAP, as CI runs it:

- each case a debt names is a case of the debts' tests (indexer/tests/test_*_debts.py), and each case there is named
  by a debt; each of those files marks its cases as strict xfails;
- a debt's due is `F1.2`, a `fix(<scope>)` PR before F1.2 (`fix(csharp)`, `fix(go)`, ...), a step of H5 (`H5 step 6`),
  or `closed`;
- the ROADMAP's list of the debts due in F1.2 ("Debts due here:"), of those due in a step of H5 ("due in an H5 step")
  and of those due in each scope's `fix` PRs ("due in a `fix(go)` PR before F1.2", "are due in `fix(csharp)` PRs
  before F1.2") are the open debts of that due, and no document names a debt the register lacks. A scope's list is
  required while a debt is due there.

Prints Markdown for the job summary; exits 1 when it finds anything. It reads files only: no Docker, no network.

    python3 -I indexer/scripts/debts.py [--root DIR]
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
HERE_MARK = "Debts due here:"
H5_MARK = "due in an H5 step"
FIX = re.compile(r"`(fix\([a-z]+\))`")
FIX_LIST = re.compile(r"due in (?:a )?`(fix\([a-z]+\))` PRs? before F1\.2")


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
        rows.append({"id": cells[0], "due": cells[3], "cases": CASE_ID.findall(cells[4])})
    ids = [r["id"] for r in rows]
    found += [f"{i}: listed twice" for i in sorted(set(ids)) if ids.count(i) > 1]
    return rows, found


def phase(due: str) -> str:
    if due.lower().startswith("closed"):
        return "closed"
    if due.startswith("F1.2"):
        return "F1.2"
    if due.startswith("H5 step"):
        return "H5"
    fix = FIX.search(due)
    return fix.group(1) if fix else "?"


def due_in(name: str) -> str:
    return {"F1.2": "F1.2", "H5": "an H5 step"}.get(name, f"a `{name}` PR before F1.2")


def mark(name: str) -> str:
    return {"F1.2": HERE_MARK, "H5": H5_MARK}.get(name, f"due in a `{name}` PR before F1.2")


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


def _ending_at(flat: str, at: int) -> set[str]:
    """The debts named in the clause that a mark starting at `at` ends."""
    head = flat[:at]
    return listed(head[max(head.rfind(c) for c in ";.)") + 1:])


def roadmap_lists(text: str) -> dict[str, set[str] | None]:
    """The debts each due's list names: F1.2's after its mark, an H5 step's and each scope's `fix` PRs' in the clause
    their mark ends. F1.2's and the H5 step's are None when the ROADMAP has no such list."""
    flat = " ".join(text.split())
    here, h5 = flat.find(HERE_MARK), flat.find(H5_MARK)
    lists = {"F1.2": listed(flat[here + len(HERE_MARK):].split("(")[0]) if here >= 0 else None,
             "H5": _ending_at(flat, h5) if h5 >= 0 else None}
    for m in FIX_LIST.finditer(flat):
        lists.setdefault(m.group(1), _ending_at(flat, m.start()))
    return lists


def _check_list(name: str, want: set[str], got: set[str] | None) -> list[str]:
    if got is None:
        return [f"the ROADMAP has no `{mark(name)}` list of the debts due in {due_in(name)}"]
    return ([f"the ROADMAP's list of the debts due in {due_in(name)} lacks {i}" for i in sorted(want - got)]
            + [f"the ROADMAP's list of the debts due in {due_in(name)} names {i}, which is not open and due there"
               for i in sorted(got - want)])


def check_cases(rows: list[dict], cases: dict[str, str]) -> list[str]:
    named = {c for r in rows for c in r["cases"]}
    found = [f"{r['id']}: names `{c}`, which no debts' test has" for r in rows for c in r["cases"] if c not in cases]
    found += [f"`{c}` ({f}) is named by no debt" for c, f in sorted(cases.items()) if c not in named]
    found += [f"{r['id']}: names no case" for r in rows if not r["cases"] and phase(r["due"]) != "closed"]
    return found


def check_roadmap(rows: list[dict], text: str, docs: dict[str, str]) -> list[str]:
    found = [f"{r['id']}: a due the check does not know ({r['due']!r}): F1.2, a `fix(<scope>)` PR, an H5 step, or "
             "closed" for r in rows if phase(r["due"]) == "?"]
    lists = roadmap_lists(text)
    fixes = sorted(({phase(r["due"]) for r in rows} | set(lists)) - {"F1.2", "H5", "closed", "?"})
    for name in ["F1.2", *fixes, "H5"]:
        found += _check_list(name, {r["id"] for r in rows if phase(r["due"]) == name}, lists.get(name))
    known = {r["id"] for r in rows}
    for doc, body in sorted(docs.items()):
        found += [f"{doc} names {i}, which the register lacks" for i in sorted(listed(body) - known)]
    return found


def check(root: Path) -> tuple[list[str], str]:
    rows, found = register((root / "docs" / "tech-debt.md").read_text())
    cases, more = debt_cases(root / "indexer" / "tests")
    docs = {str(p.relative_to(root)): p.read_text() for p in sorted((root / "docs").rglob("*.md"))
            if p.name != "tech-debt.md"}
    found += more + check_cases(rows, cases)
    found += check_roadmap(rows, (root / "docs" / "ROADMAP.md").read_text(), docs)
    closed = sum(phase(r["due"]) == "closed" for r in rows)
    return found, f"{len(rows)} debts ({len(rows) - closed} open, {closed} closed); {len(cases)} cases in the debts' tests"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ROOT)
    found, summary = check(ap.parse_args(argv).root)
    print("### Technical debts\n")
    print(summary + ("" if not found else f"; {len(found)} finding(s):\n"))
    for line in found:
        print(f"- {line}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
