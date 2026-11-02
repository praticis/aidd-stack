"""What the HTTP corpus's report sums across repositories (`scripts/http_corpus.py`): precision and recall per
language, and the gaps by category with the repositories each shows up in."""
from __future__ import annotations

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_metrics as M  # noqa: E402


def pct(v: float | None) -> str:
    return "  —  " if v is None else f"{v:5.1%}"


def _ratio(a: int, b: int) -> str:
    return pct(a / b if b else None)


class Totals:
    def __init__(self) -> None:
        self.pooled: dict[str, dict[str, collections.Counter]] = collections.defaultdict(
            lambda: {k: collections.Counter() for k in M.KINDS})
        self.gaps: dict[tuple[str, str], collections.Counter] = collections.defaultdict(collections.Counter)
        # breadth, so one big repo does not rank alone
        self.gap_repos: dict[tuple[str, str], set[str]] = collections.defaultdict(set)

    def pool(self, language: str, kind: str, **counts: int) -> None:
        self.pooled[language][kind].update(counts)

    def gap(self, kind: str, category: str | None, which: str, repo: str) -> None:
        key = (kind, category or "uncategorized")
        self.gaps[key][which] += 1
        self.gap_repos[key].add(repo)

    def print_tables(self) -> None:
        if self.pooled:
            self._print_pooled()
        if self.gaps:
            self._print_gaps()

    def _print_pooled(self) -> None:
        print(f"\n{'language':8} {'kind':10} {'P checked':>16} {'P expected':>16} {'R expected':>16}")
        for lang, kinds in sorted(self.pooled.items()):
            for k, c in kinds.items():
                if c:
                    print(f"{lang:8} {k:10} {_ratio(c['ok'], c['judged'])} {c['ok']:>4}/{c['judged']:<4} "
                          f"{_ratio(c['tp_x'], c['extracted'])} {c['tp_x']:>4}/{c['extracted']:<4} "
                          f"{_ratio(c['tp_e'], c['expected'])} {c['tp_e']:>4}/{c['expected']:<4}")

    def _print_gaps(self) -> None:
        print(f"\n{'kind':10} {'category':28} {'wrong':>5} {'fn':>4} {'repos':>5}   (wrong: checked items judged wrong · "
              "fn: distinct expected pairs missed · repos: where it shows up)")
        for (k, c), n in sorted(self.gaps.items(), key=lambda kv: (kv[0][0], -(kv[1]["wrong"] + kv[1]["fn"]), kv[0][1])):
            print(f"{k:10} {c:28} {n['wrong']:5} {n['fn']:4} {len(self.gap_repos[(k, c)]):5}")
