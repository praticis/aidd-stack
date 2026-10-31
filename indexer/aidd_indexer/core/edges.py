"""The edges the resolver gives: a `CALLS` edge with the evidence that found it, one per caller, callee, line and
method; an `IMPORTS` edge; and the external package an import may reach."""

from __future__ import annotations

from dataclasses import dataclass

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


def one_per_edge(calls: list[CallEdge]) -> list[CallEdge]:
    """One `CALLS` edge per caller, callee, line and method, by the strongest strategy of the calls that give it."""
    out: dict[tuple, CallEdge] = {}
    for c in calls:
        key = (c.caller_id, c.callee_id, c.line, c.method)
        if key not in out or _strength(c.strategy) < _strength(out[key].strategy):
            out[key] = c
    return list(out.values())


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
