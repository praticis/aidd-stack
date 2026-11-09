#!/usr/bin/env python3
"""Refuses a growth file of docs/ that has passed its ceiling.

The ceilings are a list, `docs_ceilings.txt` beside this file: one per line, `path :: size :: reason`; the path is from the
repository's root, the size is in bytes or in KB (`106 KB`, 1 KB being 1024 bytes), and a line that starts with `#` is a
comment. A file at its ceiling passes. To raise one is a line of the list, so a diff shows it. Bytes, not lines: a file of
a few long rows is as heavy as one of many short ones.

    python3 -I indexer/scripts/checks/docs_size.py [--root DIR] [--rules FILE]

Exit 0 when every file is at or under its ceiling, 1 when one is over or is missing, 2 when the list is wrong. Markdown on
stdout, for the job summary.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[3]
RULES_FILE = Path(__file__).with_name("docs_ceilings.txt")
SEPARATOR = " :: "
SIZE = re.compile(r"(\d+)\s*(KB|B)?", re.IGNORECASE)


class Ceiling(NamedTuple):
    path: str
    limit: int
    reason: str


class Row(NamedTuple):
    ceiling: Ceiling
    size: int | None

    @property
    def status(self) -> str:
        if self.size is None:
            return "missing"
        return "over" if self.size > self.ceiling.limit else "ok"


def load_ceilings(text: str) -> list[Ceiling]:
    ceilings: list[Ceiling] = []
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        parts = [p.strip() for p in raw.split(SEPARATOR, 2)]
        if len(parts) != 3 or not all(parts):
            raise ValueError(f"line {n}: expected `path :: size :: reason`")
        path, size, reason = parts
        match = SIZE.fullmatch(size)
        if not match or int(match.group(1)) == 0:
            raise ValueError(f"line {n}: the size {size!r} is not a number of bytes or of KB above zero")
        if any(c.path == path for c in ceilings):
            raise ValueError(f"line {n}: {path!r} already has a ceiling")
        limit = int(match.group(1)) * (1024 if (match.group(2) or "").upper() == "KB" else 1)
        ceilings.append(Ceiling(path, limit, reason))
    return ceilings


def measure(root: Path, ceilings: list[Ceiling]) -> list[Row]:
    return [Row(c, (root / c.path).stat().st_size if (root / c.path).is_file() else None) for c in ceilings]


def report(rows: list[Row]) -> str:
    lines = ["### Size of the growth files of docs/", "", "| File | Bytes | Ceiling | Headroom | |", "|---|---|---|---|---|"]
    for row in rows:
        c = row.ceiling
        size = "missing" if row.size is None else f"{row.size:,}"
        room = "" if row.size is None else f"{c.limit - row.size:,}"
        lines.append(f"| `{c.path}` | {size} | {c.limit:,} | {room} | {row.status} |")
    for row in rows:
        c = row.ceiling
        if row.status == "over":
            lines += ["", f"`{c.path}` is {row.size - c.limit:,} bytes over its ceiling ({c.reason}). Cut it; or raise its ceiling in "
                          "`indexer/scripts/checks/docs_ceilings.txt`, a line of the diff that the author reads."]
        elif row.status == "missing":
            lines += ["", f"`{c.path}` has a ceiling and no file: fix its line in `docs_ceilings.txt` if it moved or went."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--rules", type=Path, default=RULES_FILE)
    a = p.parse_args(argv)
    try:
        ceilings = load_ceilings(a.rules.read_text())
    except ValueError as error:
        print(f"{a.rules}: {error}", file=sys.stderr)
        return 2
    rows = measure(a.root, ceilings)
    print(report(rows))
    return 1 if any(r.status != "ok" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
