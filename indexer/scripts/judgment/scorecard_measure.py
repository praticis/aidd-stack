"""What one tree's graph measures against TypeScript's checker, repo by repo: the numbers behind scorecard.py.

The checker's verdict on the edge of a call made in a TS or JS file (`ts_vs_checker.verdict`) falls in one of four classes:

  confirmed      it agrees: the callee is the declaration, its `.d.ts` pair, or the type that owns a member with no symbol
  contradicted   the checker names another declaration of the repo
  indirect       the checker names the member of a declaration file, where the edge goes to what runs
  undecided      the checker has no opinion: `none`, `outside`, or no row for the call

Counts are over edges, by strategy (`-ambiguous` is the same strategy), and no denominator moves them: a call form the graph
learns to read adds by-name edges and leaves every count of the typed ones where it was."""
from __future__ import annotations

import collections
import glob
import gzip
import json
import os
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ts_vs_checker as T  # noqa: E402

BY_NAME = ("same-file", "same-module", "unique-name")
CLASS = {"checker: another declaration": "contradicted", T.DECLARATION_FILE: "indirect"}
MIX_TYPED = ("receiver-type", "inherited")


class Metric(NamedTuple):
    name: str
    value: float
    hit: int
    of: int  # 0 for a count


class Reference(NamedTuple):
    keyed: float
    counts: collections.Counter  # (family, class) -> edges
    wins: frozenset  # the sites where a typed edge is confirmed
    recall: tuple  # (sites the checker decides where an edge is confirmed; where a typed edge is; sites the checker decides)


class Repo(NamedTuple):
    share: Metric
    reference: Reference | None


def pct(n: int, whole: int) -> float:
    return 100.0 * n / whole if whole else 0.0


def family(call: dict) -> str:
    return call["strategy"].removesuffix("-ambiguous")


def klass(verdict: str) -> str:
    if verdict in T.AGREE:
        return "confirmed"
    return CLASS.get(verdict, "undecided")


def site(call: dict) -> tuple:
    """The checker's key of the call: its file without the extension, its line and the method it names."""
    return (T.path_of(call["caller_id"]), call["line"], T.called(call))


def mix(repo: str, run: dict) -> Metric:
    typed = sum(1 for c in run["calls"] if c["strategy"].startswith(MIX_TYPED))
    return Metric(f"{repo}.typed-share", pct(typed, len(run["calls"])), typed, len(run["calls"]))


def decided(sites: dict) -> set:
    """The sites where the checker names a declaration of the repo."""
    return {key for key, declared in sites.items() if any(d != "outside" for found in declared for d in found)}


def reference(run: dict, sites: dict) -> Reference:
    ts = T.in_ts(run)
    calls = [c for c in run["calls"] if ts(c)]
    counts, wins, confirmed = collections.Counter(), set(), set()
    for c in calls:
        fam, k = family(c), klass(T.verdict(c, sites))
        if fam in T.TYPED or fam in BY_NAME:
            counts[(fam, k)] += 1
        if k == "confirmed":
            confirmed.add(site(c))
            if fam in T.TYPED:
                wins.add(site(c))
    wanted = decided(sites)
    _, _, calls_in, n = T.keyed(sites, calls)
    return Reference(pct(calls_in, n), counts, frozenset(wins), (len(wanted & confirmed), len(wanted & wins), len(wanted)))


def measure(run_dir: Path, rows_dir: Path | None) -> dict[str, Repo]:
    """Each repo of RUN_DIR's dry-runs; one with `checker-<repo>.jsonl` in ROWS_DIR also has its reference."""
    out = {}
    for path in sorted(glob.glob(str(run_dir / "*.json.gz"))):
        repo = os.path.basename(path)[: -len(".json.gz")]
        with gzip.open(path, "rt") as handle:
            run = json.load(handle)
        rows = rows_dir / f"checker-{repo}.jsonl" if rows_dir else None
        out[repo] = Repo(mix(repo, run), reference(run, T.checker_sites(str(rows))) if rows and rows.is_file() else None)
    return out


def gated(repos: dict[str, Repo]) -> dict[str, int]:
    """The counts a pull request may not move the wrong way: confirmed typed edges, contradicted ones, by strategy."""
    out = {}
    for repo, r in repos.items():
        for fam in T.TYPED:
            if r.reference and any(r.reference.counts[(fam, k)] for k in ("confirmed", "contradicted", "indirect", "undecided")):
                out[f"{repo}.{fam}.confirmed"] = r.reference.counts[(fam, "confirmed")]
                out[f"{repo}.{fam}.contradicted"] = r.reference.counts[(fam, "contradicted")]
    return out


def keyed_of(repos: dict[str, Repo]) -> dict[str, float]:
    return {repo: r.reference.keyed for repo, r in repos.items() if r.reference}


def by_name_share(ref: Reference) -> Metric:
    wrong = sum(ref.counts[(f, "contradicted")] for f in BY_NAME)
    right = sum(ref.counts[(f, "confirmed")] for f in BY_NAME)
    return Metric("by-name-contradicted", pct(wrong, wrong + right), wrong, wrong + right)


def numbers(repos: dict[str, Repo]) -> dict[str, Metric]:
    """What a tree is, with no bound: the typed share of every repo, and against the checker the recall, the by-name edges it
    contradicts, and the typed edges it does not decide or reads indirectly."""
    out = {}
    for repo, r in repos.items():
        out[f"{repo}.typed-share"] = r.share
        if r.reference is None:
            continue
        hit, typed_hit, sites = r.reference.recall
        out[f"{repo}.recall"] = Metric(f"{repo}.recall", pct(hit, sites), hit, sites)
        out[f"{repo}.typed-recall"] = Metric(f"{repo}.typed-recall", pct(typed_hit, sites), typed_hit, sites)
        share = by_name_share(r.reference)
        out[f"{repo}.{share.name}"] = share._replace(name=f"{repo}.{share.name}")
        for fam in T.TYPED:
            for k in ("indirect", "undecided"):
                n = r.reference.counts[(fam, k)]
                out[f"{repo}.{fam}.{k}"] = Metric(f"{repo}.{fam}.{k}", n, n, 0)
    return out


def lost_wins(base: dict[str, Repo], head: dict[str, Repo]) -> dict[str, list]:
    """The sites where the base has a confirmed typed edge and the head has none, by repo."""
    out = {}
    for repo, b in base.items():
        h = head.get(repo)
        if b.reference and h and h.reference and (b.reference.wins - h.reference.wins):
            out[repo] = sorted(b.reference.wins - h.reference.wins)
    return out
