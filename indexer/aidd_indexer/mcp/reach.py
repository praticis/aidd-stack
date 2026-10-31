"""Who reaches some symbols through calls, hop by hop. A symbol's callers are those that call it, and those that make a
dispatching call to a method it overrides, on a receiver that may hold an instance which runs it (`OVERRIDES` and the
`receivers` of both). The walk is the graph's calls read backwards, one hop at a time, so a dispatch may happen at any
hop of a chain."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Hop:
    caller: str
    callee: str
    strategy: str | None
    dispatch: bool              # a call to a method the callee overrides


@dataclass(frozen=True)
class Reach:
    hops: int
    via_ambiguous: bool         # some chain within the depth has a hop resolved by name among several
    via_dispatch: bool          # every chain within the depth has a dispatch that may happen


def walk(callers_of: Callable[[list[str]], Iterable[Hop]], targets: list[str], depth: int) -> dict[str, Reach]:
    """Each symbol that reaches one of `targets` in at most `depth` hops, but the targets."""
    dist = dict.fromkeys(targets, 0)
    out: dict[str, set[tuple[str, bool, bool]]] = defaultdict(set)
    frontier = list(dist)
    for k in range(1, depth + 1):
        found = []
        for h in callers_of(frontier) if frontier else ():
            out[h.caller].add((h.callee, (h.strategy or "").endswith("ambiguous"), h.dispatch))
            if h.caller not in dist:
                dist[h.caller] = k
                found.append(h.caller)
        frontier = found
    ambiguous, plain = _chains(out, dist, set(targets), depth)
    return {s: Reach(n, s in ambiguous, s not in plain) for s, n in dist.items() if n}


def _chains(out: dict[str, set[tuple[str, bool, bool]]], dist: dict[str, int], targets: set[str],
            depth: int) -> tuple[set[str], set[str]]:
    """The symbols with a chain of at most `depth` hops to a target through an ambiguous hop, and through no
    dispatch. A chain may pass a symbol twice, as a recursion runs."""
    ambiguous: set[str] = set()
    plain = set(targets)
    for b in range(1, depth + 1):
        ambiguous = {s for s, hops in out.items()
                     if any(v in ambiguous or (amb and dist.get(v, depth) < b) for v, amb, _ in hops)}
        plain = targets | {s for s, hops in out.items() if any(v in plain and not d for v, _, d in hops)}
    return ambiguous, plain
