"""A micro dry-run's CALLS edges per call site and by strategy, shared by the judgment scripts: a site is its caller's
file and the call's line, and its edges are (callee's qualified name, strategy)."""
import collections
import gzip
import json
import random
import sys
import typing

# the resolver's mark on an edge to one of several homonyms a call found by name could reach
AMBIGUOUS = "-ambiguous"


def load(d, repo):
    return json.load(gzip.open(f"{d}/{repo}.json.gz", "rt"))


def edges(run):
    files = {f["id"]: f["path"] for f in run["files"]}
    sym = {s["id"]: s for s in run["symbols"]}
    out = {}
    for c in run["calls"]:
        caller = sym.get(c["caller_id"])
        f = files.get(caller["file_id"]) if caller else None
        if f is None:                                  # a call from a file, not from a symbol
            f = files.get(c["caller_id"], "?")
        callee = sym.get(c["callee_id"], {}).get("qualified_name", c["callee_id"])
        out.setdefault((f, c["line"]), set()).add((callee, c["strategy"]))
    return out


class Strategies(typing.NamedTuple):
    edges: collections.Counter      # strategy -> edges
    sites: int
    ambiguous_sites: int            # sites with an edge to one of several homonyms the call could reach

    @property
    def ambiguous_edges(self) -> int:
        return sum(n for strategy, n in self.edges.items() if strategy.endswith(AMBIGUOUS))


def strategies(run, language=None) -> Strategies:
    """The CALLS edges of a dry-run by strategy, and its call sites; with `language`, only the calls made in that
    language's files. A line with two calls is one site, ambiguous when either call is."""
    files = {f["id"]: f for f in run["files"]}
    sym = {s["id"]: s for s in run["symbols"]}
    by_strategy, sites = collections.Counter(), {}
    for c in run["calls"]:
        caller = sym.get(c["caller_id"])
        f = files.get(caller["file_id"] if caller else c["caller_id"])
        if language is not None and (f is None or f.get("language") != language):
            continue
        by_strategy[c["strategy"]] += 1
        site = (f["path"] if f else "?", c["line"])
        sites[site] = sites.get(site, False) or c["strategy"].endswith(AMBIGUOUS)
    return Strategies(by_strategy, len(sites), sum(sites.values()))



def kind(was: set, now: set) -> str:
    """How a site changed: the same callees by another strategy, or callees added, dropped, widened, narrowed or changed."""
    cw, cn = {c for c, _ in was}, {c for c, _ in now}
    if cw == cn:
        return "strategy"
    if not cw:
        return "added"
    if not cn:
        return "dropped"
    return "widened" if cw < cn else "narrowed" if cn < cw else "changed"


def changed(before: dict, after: dict) -> list:
    """The sites whose edges differ between two dry-runs of a repo, as ((file, line), was, now)."""
    b, a = edges(before), edges(after)
    # sorted: a set's order changes from one process to the next, and the seeded samples are drawn in this order
    return [(key, b.get(key, set()), a.get(key, set())) for key in sorted(set(b) | set(a))
            if b.get(key, set()) != a.get(key, set())]
