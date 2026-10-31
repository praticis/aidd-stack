"""The edges the resolver gives: a `CALLS` edge with the evidence that found it, one per caller, callee, line and
method, whether the object's class may choose the method it runs, and the receiver's types when the method is a
supertype's; an `IMPORTS` edge; and the external package an import may reach."""

from __future__ import annotations

from dataclasses import dataclass, replace

# strongest evidence first: the receiver's type, the message's, a base outside the repo, then the nearest homonym
EVIDENCE = ("receiver-type", "receiver-type-impl", "dispatch", "inherited", "inherited-impl",
            "same-file", "same-module", "unique-name")


@dataclass
class CallEdge:
    caller_id: str
    callee_id: str
    line: int
    strategy: str          # one of EVIDENCE, + "-ambiguous" when the target is one of several
    method: str | None = None   # inherited*: the method called, which the repo does not declare (it comes from a package base)
    virtual: bool = True        # False: the language sends the call to one method by name (`base.M()`, `super().m()`)
    receivers: tuple[str, ...] = ()     # the receiver's types, when a supertype's method: which overrides it may run


def one_per_edge(calls: list[CallEdge]) -> list[CallEdge]:
    """One `CALLS` edge per caller, callee, line and method, by the strongest strategy of the calls that give it; it may
    dispatch when one of them may, on the receivers of each, and on any when one's receiver is the declaring type."""
    out: dict[tuple, CallEdge] = {}
    for c in calls:
        key = (c.caller_id, c.callee_id, c.line, c.method)
        kept = out.get(key, c)
        best = c if _strength(c.strategy) < _strength(kept.strategy) else kept
        receivers = tuple(sorted({*kept.receivers, *c.receivers})) if kept.receivers and c.receivers else ()
        out[key] = replace(best, virtual=kept.virtual or c.virtual, receivers=receivers)
    return list(out.values())


def on_receivers(calls: list[CallEdge], overridden: set[str]) -> list[CallEdge]:
    """The calls, their receivers kept only where they decide a dispatch: on a call that may dispatch to a method
    another overrides."""
    return [c if not c.receivers or (c.virtual and c.callee_id in overridden) else replace(c, receivers=())
            for c in calls]


def _strength(strategy: str) -> tuple[int, bool]:
    return EVIDENCE.index(strategy.removesuffix("-ambiguous")), strategy.endswith("-ambiguous")


@dataclass
class ImportEdge:
    file_id: str
    target_id: str
    target_label: str      # File | Module | Package
    line: int
    spec: str


@dataclass
class PackageNode:
    id: str
    name: str
    ecosystem: str         # go | npm | pypi | nuget
    stdlib: bool
