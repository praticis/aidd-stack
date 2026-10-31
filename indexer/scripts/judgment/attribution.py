#!/usr/bin/env python3
"""Which answer explains each CALLS edge that changed between two dry-runs. A change to how a language types a receiver,
or to what the resolver makes of it, changes edges at the sites where that answer changes, and nowhere else, so a
changed edge at a site whose answers are the same on both sides is not explained by them, and is listed apart.

    attribution.py BEFORE AFTER OLD.jsonl NEW.jsonl N REPO... [--cases FILE] [--repos DIR] [--language LANG]

BEFORE and AFTER hold `<repo>.json.gz` dry-runs. OLD.jsonl and NEW.jsonl hold what each side answers at a call, one JSON
object per line, as `answers.py` writes them: repo, file, line, receiver, type, the reason it has none (unknown), what
the resolver makes of the receiver (resolved), src, and any fact the case table reads. A side with no row for a
receiver, or no type in it, does not type it, and with no `resolved` goes by name on it. FILE defines `case_of(d)` for
a site whose answer differs (d: repo, file, line, receiver, old and new types, old_resolved, new_resolved, src and the
facts) and returns its case, or None for the answer's own: typed-now, untyped-now or retyped when the type differs, else
the resolver's answer on each side by kind (`package -> by name`, `by name -> type`). Prints the changed sites by case
and kind, then N seeded samples of each case and kind that changes a callee, and the first N unexplained sites, with
--repos DIR their source lines. Last, each repo's CALLS edges by strategy on both sides, and the share of edges and of
sites the resolver found among several homonyms (`-ambiguous`); with --language LANG, a language's id or several
separated by commas, of the calls made in their files only. Then the receivers each side leaves untyped by the reason it
gives."""
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
    """The sites where the two sides answer differently, by the first receiver whose type or resolver's answer differs.
    A receiver one side has no row for is untyped there, and goes by name; the row keeps the facts of the side that has
    it."""
    out = {}
    for site in sorted(set(old) | set(new)):
        a, b = old.get(site, {}), new.get(site, {})
        for receiver in sorted(set(a) | set(b)):
            was, now = a.get(receiver, {}), b.get(receiver, {})
            if (was.get("type"), was.get("resolved")) != (now.get("type"), now.get("resolved")):
                row = {k: v for k, v in (now or was).items() if k not in ("type", "resolved")}
                out[site] = {**row, "old": was.get("type"), "new": now.get("type"),
                             "old_resolved": was.get("resolved"), "new_resolved": now.get("resolved")}
                break
    return out


def default_case(d: dict) -> str:
    if d["old"] != d["new"]:
        if d["old"] is None:
            return "typed-now"
        return "untyped-now" if d["new"] is None else "retyped"
    return f"{resolver_kind(d.get('old_resolved'))} -> {resolver_kind(d.get('new_resolved'))}"


def resolver_kind(answer: Optional[str]) -> str:
    return answer.split(" ", 1)[0] if answer else "by name"


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
                d = r["answer"]
                lines.append(f"   type {d['old']} -> {d['new']}  ({d['receiver']})")
                if d.get("old_resolved") != d.get("new_resolved"):
                    lines.append(f"   resolved {d.get('old_resolved')} -> {d.get('new_resolved')}")
            lines += [f"   was {r['was']}", f"   now {r['now']}"]
    return lines


def share(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f} %" if whole else "-"


def strategy_table(repo: str, before: dict, after: dict, language: Optional[str]) -> list:
    b, a = L.strategies(before, language), L.strategies(after, language)
    eb, ea = sum(b.edges.values()), sum(a.edges.values())
    rows = [(s, b.edges[s], a.edges[s]) for s in sorted(set(b.edges) | set(a.edges))]
    rows += [("edges", eb, ea), ("ambiguous edges", share(b.ambiguous_edges, eb), share(a.ambiguous_edges, ea)),
             ("sites", b.sites, a.sites),
             ("ambiguous sites", share(b.ambiguous_sites, b.sites), share(a.ambiguous_sites, a.sites))]
    title = f"\n{language or 'every language'}'s CALLS in {repo}, by strategy"
    return [title, f"  {'':26} {'before':>9} {'after':>9}"] + [f"  {name:26} {x:>9} {y:>9}" for name, x, y in rows]


def reasons_table(old: dict, new: dict) -> list:
    """The receivers each side leaves untyped, by the reason the language gives, the most frequent after the change first."""
    def count(side: dict) -> collections.Counter:
        return collections.Counter(r["unknown"] for receivers in side.values() for r in receivers.values()
                                   if r.get("unknown"))
    b, a = count(old), count(new)
    reasons = sorted(set(b) | set(a), key=lambda reason: (-a[reason], -b[reason], reason))
    width = max([26] + [len(reason) for reason in reasons])
    lines = [f"  {reason:{width}} {b[reason]:>9} {a[reason]:>9}" for reason in reasons] or ["  no side gives one"]
    return ["\nreceivers with no type, by the reason the language gives",
            f"  {'':{width}} {'before':>9} {'after':>9}"] + lines


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("before", "after", "old", "new"):
        ap.add_argument(name)
    ap.add_argument("n", type=int)
    ap.add_argument("names", nargs="+", metavar="REPO")
    ap.add_argument("--cases")
    ap.add_argument("--repos")
    ap.add_argument("--language")
    return ap


def main(argv: list) -> int:
    a = parser().parse_args(argv)
    try:
        old, new = read_answers(a.old), read_answers(a.new)
        case_of, diffs = load_cases(a.cases), differences(old, new)
        rows, strategy_lines = [], []
        for repo in a.names:
            before, after = L.load(a.before, repo), L.load(a.after, repo)
            mine = explain(repo, before, after, diffs, case_of)
            unexplained = sum(r["case"] == UNEXPLAINED for r in mine)
            print(f"{len(mine)} changed site(s) in {repo}, {unexplained} unexplained")
            rows += mine
            strategy_lines += strategy_table(repo, before, after, a.language)
    except (AttributionError, OSError) as e:
        print(f"attribution: {e}", file=sys.stderr)
        return 2
    print("\n" + "\n".join(table(rows) + samples(rows, a.n, a.repos) + strategy_lines + reasons_table(old, new)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
