"""Who reaches some symbols through calls, hop by hop. A symbol's callers are those that call it, and those that make a
dispatching call to a method it overrides, on a receiver that may hold an instance which runs it (`OVERRIDES` and the
`receivers` of both). The walk is the graph's calls read backwards, one hop at a time, so a dispatch may happen at any
hop of a chain. A caller is marked only when every chain to it has the mark: one chain without it reaches it as well."""

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
    via_ambiguous: bool         # every chain within the depth has a hop resolved by name among several
    via_dispatch: bool          # every chain within the depth has a dispatch that may happen


def walk(callers_of: Callable[[list[str]], Iterable[Hop]], targets: list[str], depth: int) -> dict[str, Reach]:
    """Each symbol that reaches one of `targets` in at most `depth` hops, but the targets."""
    dist = dict.fromkeys(targets, 0)
    out: dict[str, set[Hop]] = defaultdict(set)
    frontier = list(dist)
    for k in range(1, depth + 1):
        found = []
        for h in callers_of(frontier) if frontier else ():
            out[h.caller].add(h)
            if h.caller not in dist:
                dist[h.caller] = k
                found.append(h.caller)
        frontier = found
    proven = _reached(out, set(targets), depth, lambda h: not (h.strategy or "").endswith("ambiguous"))
    plain = _reached(out, set(targets), depth, lambda h: not h.dispatch)
    return {s: Reach(n, s not in proven, s not in plain) for s, n in dist.items() if n}


def _reached(out: dict[str, set[Hop]], targets: set[str], depth: int, keep: Callable[[Hop], bool]) -> set[str]:
    """The targets, and the symbols with a chain of at most `depth` hops to one on which `keep` holds every hop."""
    reached = targets
    for _ in range(depth):
        reached = targets | {s for s, hops in out.items() if any(h.callee in reached and keep(h) for h in hops)}
    return reached
