#!/usr/bin/env python3
"""Which answer explains each CALLS edge that changed between two dry-runs. A change to how a language types a receiver
changes edges at the sites where the typing answer changes, and nowhere else, so a changed edge at a site whose answer
is the same on both sides is not explained by it, and is listed apart.

    attribution.py BEFORE AFTER OLD.jsonl NEW.jsonl N REPO... [--cases FILE] [--repos DIR]

BEFORE and AFTER hold `<repo>.json.gz` dry-runs. OLD.jsonl and NEW.jsonl hold what each side answers at a call, one JSON
object per line, as `answers.py` writes them: repo, file, line, receiver, type, src, and any fact the case table
reads. A side with no row for a receiver does not type it. FILE defines `case_of(d)` for a site whose answer differs
(d: repo, file, line, receiver, old, new, src and the facts) and returns its case, or None for the answer's own:
typed-now, untyped-now or retyped. Prints the changed sites by case and kind, then N seeded samples of each case and kind
that changes a callee, and the first N unexplained sites, with --repos DIR their source lines."""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import os
import random
import sys
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edges_lib as L  # noqa: E402

SEED = 20261021
UNEXPLAINED = "unexplained"
Site = tuple


class AttributionError(Exception):
    pass


def read_answers(path: str) -> dict:
    """site (repo, file, line) → receiver → the row, from a JSON lines file."""
    out: dict = {}
    with open(path) as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                out.setdefault((row["repo"], row["file"], row["line"]), {})[row["receiver"]] = row
    return out


def differences(old: dict, new: dict) -> dict:
    """The sites where the two sides answer differently, by the first receiver whose type differs. A receiver one side
    does not type is untyped there; the row keeps the facts of the side that has it."""
    out = {}
    for site in sorted(set(old) | set(new)):
        a, b = old.get(site, {}), new.get(site, {})
        for receiver in sorted(set(a) | set(b)):
            before, after = a.get(receiver, {}).get("type"), b.get(receiver, {}).get("type")
            if before != after:
                row = {k: v for k, v in (b.get(receiver) or a[receiver]).items() if k != "type"}
                out[site] = {**row, "old": before, "new": after}
                break
    return out


def default_case(d: dict) -> str:
    if d["old"] is None:
        return "typed-now"
    return "untyped-now" if d["new"] is None else "retyped"


def load_cases(path: Optional[str]) -> Callable[[dict], str]:
    if path is None:
        return default_case
    spec = importlib.util.spec_from_file_location("cases", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "case_of"):
        raise AttributionError(f"{path} defines no case_of(d)")
    return lambda d: module.case_of(d) or default_case(d)


def explain(repo: str, before: dict, after: dict, diffs: dict, case_of: Callable[[dict], str]) -> list:
    """Each changed site of a repo with the case of the answer that differs there, or `unexplained`."""
    rows = []
    for (file, line), was, now in L.changed(before, after):
        answer = diffs.get((repo, file, line))
        rows.append({"repo": repo, "file": file, "line": line, "kind": L.kind(was, now), "answer": answer,
                     "case": case_of(answer) if answer else UNEXPLAINED, "was": sorted(was), "now": sorted(now)})
    return rows


def source(root: Optional[str], row: dict) -> str:
    if row["answer"]:
        return row["answer"]["src"]
    try:
        return (Path(root) / row["repo"] / row["file"]).read_text(errors="replace").splitlines()[row["line"] - 1].strip()[:160]
    except (OSError, IndexError, TypeError):
        return ""


def table(rows: list) -> list:
    counts = collections.Counter((r["case"], r["kind"]) for r in rows)
    return [f"{'case':26} {'kind':9} sites"] + [f"{case:26} {kind:9} {n}" for (case, kind), n in sorted(counts.items())]


def samples(rows: list, n: int, root: Optional[str]) -> list:
    """N seeded rows of each case and kind that changes a callee, and the first N unexplained ones."""
    groups = collections.defaultdict(list)
    for r in rows:
        if r["case"] == UNEXPLAINED or r["kind"] != "strategy":
            groups[(r["case"], r["kind"])].append(r)
    rng, lines = random.Random(SEED), []
    for (case, kind), items in sorted(groups.items()):
        for r in items[:n] if case == UNEXPLAINED else rng.sample(items, min(n, len(items))):
            lines.append(f"\n[{case} / {kind}] {r['repo']} {r['file']}:{r['line']}  {source(root, r)}")
            if r["answer"]:
                lines.append(f"   type {r['answer']['old']} -> {r['answer']['new']}  ({r['answer']['receiver']})")
            lines += [f"   was {r['was']}", f"   now {r['now']}"]
    return lines


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("before", "after", "old", "new"):
        ap.add_argument(name)
    ap.add_argument("n", type=int)
    ap.add_argument("names", nargs="+", metavar="REPO")
    ap.add_argument("--cases")
    ap.add_argument("--repos")
    return ap


def main(argv: list) -> int:
    a = parser().parse_args(argv)
    try:
        case_of, diffs = load_cases(a.cases), differences(read_answers(a.old), read_answers(a.new))
        rows = []
        for repo in a.names:
            mine = explain(repo, L.load(a.before, repo), L.load(a.after, repo), diffs, case_of)
            print(f"{len(mine)} changed site(s) in {repo}, {sum(r['case'] == UNEXPLAINED for r in mine)} unexplained")
            rows += mine
    except (AttributionError, OSError) as e:
        print(f"attribution: {e}", file=sys.stderr)
        return 2
    print("\n" + "\n".join(table(rows) + samples(rows, a.n, a.repos)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
