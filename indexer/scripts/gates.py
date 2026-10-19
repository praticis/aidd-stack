#!/usr/bin/env python3
"""The method's gates over two corpus runs, the base's and the branch's, as CI runs them on a pull request:

- the precision ratchet: no repository's and no language's list precision is lower on the branch;
- no win lost: no expected pair the base found is missed, and no checked item judged right is gone;
- the hold-out untouched, unless the pull request carries the `holdout-measurement` label;
- a refactor changes nothing: with the `refactor` label, any difference fails.

Every other difference is classified the way a judgment starts: a gain (an expected pair now found) or an item to
judge at its source, linked to its line. Both runs are scored against the branch's expected lists. The hold-out's
items are never listed, only whether it changed. Prints Markdown for the job summary; exits 1 when a gate fails.

    python scripts/gates.py --base RUNS --head RUNS [--holdout-base RUNS --holdout-head RUNS | --holdout-changed N]
                            [--label NAME ...]
    python scripts/gates.py --holdout-base RUNS --holdout-head RUNS --holdout-count     # only how many changed

CI counts the hold-out's changes where it runs it, so that no artifact carries the hold-out's items.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_metrics as M  # noqa: E402
import http_corpus as H  # noqa: E402

GATES = ("Precision ratchet", "No win lost", "Hold-out untouched", "A refactor changes nothing", "Every repo measured")


@dataclass
class Findings:
    failed: dict[str, list[str]] = field(default_factory=lambda: {g: [] for g in GATES})
    gains: list[str] = field(default_factory=list)
    to_judge: list[str] = field(default_factory=list)
    differ: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # language -> kind -> [base true positives, base extracted, head true positives, head extracted]
    pooled: dict = field(default_factory=lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: [0] * 4)))


def load_runs(d: Path | None) -> dict[str, dict]:
    return {f.stem: json.loads(f.read_text()) for f in sorted(d.glob("*.json"))} if d else {}


def _where(run: dict, evidence: str) -> str:
    """`repo:path/file.go:12` as a link to that line at the pinned commit."""
    file, line = M.evidence_file(evidence), evidence.rsplit(":", 1)[-1]
    return f"[{file}:{line}](https://github.com/{run['repo']}/blob/{run['sha']}/{file}#L{line})"


def _item(name: str, kind: str, key: tuple, run: dict) -> str:
    return f"{name} {kind} `{key[0]} {key[1]}` {_where(run, key[2])}"


def _hits(k: tuple[str, str], keys: set[tuple[str, str]]) -> bool:
    low = (k[0], k[1].lower())
    return any(M._matches(k, j) or M._matches(low, (j[0], j[1].lower())) for j in keys)


def _share(tp: int, n: int) -> str:
    return f"{tp / n:.1%} ({tp}/{n})"


def _ratchet(name: str, kind: str, sb: M.Score, sh: M.Score, f: Findings) -> None:
    tb, th = sb.extracted - len(sb.false_positives), sh.extracted - len(sh.false_positives)
    if sb.extracted and sh.extracted and Fraction(th, sh.extracted) < Fraction(tb, sb.extracted):
        f.failed["Precision ratchet"].append(f"{name} {kind}: {_share(tb, sb.extracted)} → {_share(th, sh.extracted)}")


@dataclass
class Listed:
    """One kind of one repository against its expected list: the pairs it now finds and misses, and the list."""
    gained: set = field(default_factory=set)
    lost: set = field(default_factory=set)
    expected: set | None = None

    def tag(self, key: tuple, verb: str) -> str:
        if self.expected is None:
            return f"{verb}, no list"
        return f"{verb}, {'another place of an expected pair' if _hits(key[:2], self.expected) else 'outside the list'}"


def _listed(name: str, kind: str, base: dict, head: dict, gab: dict | None, f: Findings) -> Listed:
    if gab is None or kind not in gab:
        return Listed()
    sb, sh = M.score(base, gab, kind), M.score(head, gab, kind)
    _ratchet(name, kind, sb, sh, f)
    lost = set(sh.false_negatives) - set(sb.false_negatives)
    f.failed["No win lost"] += [f"{name} {kind}: expected `{m} {p}` no longer found" for m, p in sorted(lost)]
    return Listed(set(sb.false_negatives) - set(sh.false_negatives), lost, {M.item_key(i) for i in gab[kind]})


def _classify(name: str, kind: str, base: dict, head: dict, gab: dict | None, f: Findings) -> None:
    """The diff's items: gains, wins lost (a gate) and items to judge."""
    d = M.diff_runs(base, head, kind)
    if not d:
        return
    ls = _listed(name, kind, base, head, gab, f)
    for key in d.added:
        if _hits(key[:2], ls.gained):
            f.gains.append(_item(name, kind, key, head))
        else:
            f.to_judge.append(f"{ls.tag(key, 'new')}: {_item(name, kind, key, head)}")
    f.to_judge += [f"{ls.tag(key, 'gone')}: {_item(name, kind, key, base)}" for key in d.removed
                   if not _hits(key[:2], ls.lost)]
    f.to_judge += [f"{M.SECONDARY[kind]} changed: {_item(name, kind, key, head)}" for key in d.resolution]


def _checked(name: str, base: dict, head: dict, gab: dict, f: Findings) -> None:
    """A sampled item judged right that the base extracted and the branch does not."""
    for kind in M.KINDS:
        cb, ch = M.checked_precision(base, gab, kind), M.checked_precision(head, gab, kind)
        if cb is None or ch is None:
            continue
        before = {M._check_id(i) for i in cb.stale}
        for i in ch.stale:
            if i.get("ok") and M._check_id(i) not in before:
                f.failed["No win lost"].append(f"{name} {kind}: checked `{i['method']} {i['path']}` at {i['evidence']} is gone")


def _pool(name: str, base: dict, head: dict, gab: dict, f: Findings) -> None:
    langs = gab.get("language") or {}
    for kind in M.KINDS:
        sb, sh = M.score(base, gab, kind), M.score(head, gab, kind)
        if sb is None or sh is None:
            continue
        c = f.pooled[langs.get(kind) or H.LANGUAGE.get(name, "?")][kind]
        for i, s in ((0, sb), (2, sh)):
            c[i] += s.extracted - len(s.false_positives)
            c[i + 1] += s.extracted


def compare_repo(name: str, base: dict, head: dict, expected: Path, f: Findings) -> None:
    if base.get("sha") != head.get("sha"):
        f.notes.append(f"{name}: the pin changed ({base.get('sha', '?')[:10]} → {head.get('sha', '?')[:10]}), so ids may "
                       "differ for that reason alone")
    gf = expected / f"{name}.json"
    gab = json.loads(gf.read_text()) if gf.exists() else None
    if any(M.diff_runs(base, head, k) for k in M.KINDS):
        f.differ.append(name)
    for kind in M.KINDS:
        _classify(name, kind, base, head, gab, f)
    if gab is not None:
        _checked(name, base, head, gab, f)
        _pool(name, base, head, gab, f)


def compare_corpus(base: dict[str, dict], head: dict[str, dict], expected: Path, f: Findings) -> None:
    for name in sorted(base.keys() - head.keys()):
        f.failed["Every repo measured"].append(f"{name}: no run on the branch (see the job's logs)")
    for name in sorted(head.keys() - base.keys()):
        f.notes.append(f"{name}: new in the corpus, nothing to compare with")
    for name in sorted(base.keys() & head.keys()):
        compare_repo(name, base[name], head[name], expected, f)
    for lang, kinds in sorted(f.pooled.items()):
        for kind, (tb, xb, th, xh) in kinds.items():
            if xb and xh and Fraction(th, xh) < Fraction(tb, xb):
                f.failed["Precision ratchet"].append(f"{lang} {kind}: {_share(tb, xb)} → {_share(th, xh)}")


def holdout_changed(base: dict[str, dict], head: dict[str, dict]) -> int:
    return sum(1 for n in base.keys() | head.keys()
               if n not in base or n not in head or any(M.diff_runs(base[n], head[n], k) for k in M.KINDS))


def judge_holdout(changed: int, labels: set[str], f: Findings) -> None:
    if changed and "holdout-measurement" not in labels:
        f.failed["Hold-out untouched"].append(f"the hold-out changed in {changed} repo(s); its items are not "
                                              "listed. Measuring it is a decision: the `holdout-measurement` label")
    elif changed:
        f.notes.append(f"the hold-out changed in {changed} repo(s), under the `holdout-measurement` label")


def render(f: Findings, labels: set[str], show: int) -> str:
    ok = not any(f.failed.values())
    out = [f"## Corpus gates: {'pass' if ok else 'FAIL'}", "", "| Gate | Result |", "|---|---|"]
    for g in GATES:
        if g == "A refactor changes nothing" and "refactor" not in labels:
            out.append(f"| {g} | not a refactor (no `refactor` label) |")
        else:
            out.append(f"| {g} | {'ok' if not f.failed[g] else f'{len(f.failed[g])} failure(s)'} |")
    out += ["", f"**{len(f.differ)} repo(s) differ**" + (f": {', '.join(f.differ)}" if f.differ else "")]
    sections = [("Failures", [x for g in GATES for x in f.failed[g]]), ("Notes", f.notes),
                (f"Gains ({len(f.gains)})", f.gains), (f"To judge at the source ({len(f.to_judge)})", f.to_judge)]
    for title, items in sections:
        if items:
            out += ["", f"### {title}", ""] + [f"- {x}" for x in items[:show]]
            out += [f"- … {len(items) - show} more"] if len(items) > show else []
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, help="the base's corpus run")
    ap.add_argument("--head", type=Path, help="the branch's corpus run")
    ap.add_argument("--holdout-base", type=Path)
    ap.add_argument("--holdout-head", type=Path)
    ap.add_argument("--holdout-changed", type=int, help="the hold-out repos that changed, counted where it ran")
    ap.add_argument("--holdout-count", action="store_true", help="print how many hold-out repos changed, and exit")
    ap.add_argument("--expected", type=Path, default=H.EXPECTED_DIR)
    ap.add_argument("--label", action="append", default=[], help="a label of the pull request (repeatable)")
    ap.add_argument("--show", type=int, default=100, help="items listed per section")
    args = ap.parse_args()
    changed = args.holdout_changed
    if changed is None:
        changed = holdout_changed(load_runs(args.holdout_base), load_runs(args.holdout_head))
    if args.holdout_count:
        print(changed)
        return 0
    if args.base is None or args.head is None:
        ap.error("--base and --head")
    labels = {x.strip() for v in args.label for x in v.split(",") if x.strip()}
    f = Findings()
    compare_corpus(load_runs(args.base), load_runs(args.head), args.expected, f)
    judge_holdout(changed, labels, f)
    if "refactor" in labels and (f.differ or changed):
        f.failed["A refactor changes nothing"].append(
            f"{len(f.differ)} corpus repo(s) and {changed} hold-out repo(s) differ under the `refactor` label")
    print(render(f, labels, args.show), end="")
    return 1 if any(f.failed.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
