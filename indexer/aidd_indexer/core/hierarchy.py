"""`EXTENDS`, `IMPLEMENTS` and `OVERRIDES` inside one repo. A type's edges go to the types of the repo it names as its
direct bases, as its language reads them (`LanguageSupport.bases`): a type that is not an interface implements an
interface it names, and extends any other base. A base declared in parts (a C# partial type) is each of its
declarations. A method's edges go to the methods a dispatching call to which may run it, on an instance of some type of
the repo at or below theirs, as the instance's language says (`LanguageSupport.dispatched`), with the types below the
target's a receiver of which may hold such an instance. Two types of one qualified name (C#'s `IFoo` and `IFoo<T>` in
one file) are told apart by no name a base writes: neither has an edge, nor do their methods."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from .. import languages
from ..languages.base import ResolveContext
from .model import FileInfo, SymbolInfo


@dataclass(frozen=True, order=True)
class HierarchyEdge:
    source_id: str
    target_id: str
    kind: str                       # EXTENDS | IMPLEMENTS | OVERRIDES
    receivers: tuple[str, ...] = ()     # OVERRIDES: the types below the target's a call on which may run the source


@dataclass(frozen=True)
class Declared:
    """The repo's types a dispatch is read from, by qualified name and by id, each type's methods, and its direct bases
    of the repo by qualified name."""
    types: dict[str, SymbolInfo]
    by_id: dict[str, SymbolInfo]
    methods: dict[str, list[SymbolInfo]]
    bases: dict[str, list[str]]


def type_edges(types: list[SymbolInfo], files_by_id: dict[str, FileInfo], ctx: ResolveContext) -> list[HierarchyEdge]:
    """The edges from each of `types` to the declarations of its bases, sorted."""
    declared: dict[str, list[SymbolInfo]] = defaultdict(list)
    for t in types:
        declared[t.qualified_name].append(t)
    shared = _shared(types)
    read: dict[tuple[str, str], list[str]] = {}     # a partial type's parts ask once
    edges = set()
    for t in (t for t in types if t.qualified_name not in shared):
        language = files_by_id[t.file_id].language
        if (language, t.qualified_name) not in read:
            support = languages.by_id(language)
            read[language, t.qualified_name] = support.bases(ctx, t.qualified_name) if support is not None else []
        edges |= {HierarchyEdge(t.id, b.id, _kind(t, b)) for q in read[language, t.qualified_name] if q not in shared
                  for b in declared.get(q, ()) if b.id != t.id}
    return sorted(edges)


def override_edges(types: list[SymbolInfo], methods: list[SymbolInfo], edges: list[HierarchyEdge],
                   files_by_id: dict[str, FileInfo], ctx: ResolveContext) -> list[HierarchyEdge]:
    """`OVERRIDES` from each method a dispatching call may run instead of another, sorted. Only a method whose name a
    type of the instance's ancestry declares again is asked about."""
    up: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        up[e.source_id].add(e.target_id)
    declared = _declared(types, methods, up)
    above = {t: _ancestors(up, t) & declared.by_id.keys() for t in declared.by_id}
    on: dict[tuple[str, str, str], set[str]] = defaultdict(set)     # where a call to the target runs the source
    for d in declared.by_id.values():
        support = languages.by_id(files_by_id[d.file_id].language)
        again = Counter(m.name for t in above[d.id] | {d.id}
                        for m in declared.methods.get(declared.by_id[t].qualified_name, ()))
        asked = [o for t in above[d.id] for o in declared.methods.get(declared.by_id[t].qualified_name, ())
                 if again[o.name] > 1]
        for o in asked if support is not None else ():
            for m in support.dispatched(ctx, declared, d.qualified_name, o):
                if m.id != o.id:
                    on[m.id, o.id, o.parent_id].add(d.id)
    return sorted(HierarchyEdge(m, o, "OVERRIDES", _receivers(declared, above, ds, owner))
                  for (m, o, owner), ds in on.items())


def _declared(types: list[SymbolInfo], methods: list[SymbolInfo], up: dict[str, set[str]]) -> Declared:
    shared = _shared(types)
    by_id = {t.id: t for t in types if t.qualified_name not in shared}
    owned: dict[str, list[SymbolInfo]] = defaultdict(list)
    for m in methods:
        if m.parent_id in by_id:
            owned[by_id[m.parent_id].qualified_name].append(m)
    bases = {t.qualified_name: sorted(by_id[b].qualified_name for b in up.get(i, ()) if b in by_id)
             for i, t in by_id.items()}
    return Declared({t.qualified_name: t for t in by_id.values()}, by_id, dict(owned), bases)


def _receivers(declared: Declared, above: dict[str, set[str]], instances: set[str], owner: str) -> tuple[str, ...]:
    """The types below `owner` that are one of `instances` or above one: a receiver of such a type may hold it."""
    return tuple(sorted({declared.by_id[t].qualified_name for d in instances for t in above[d] | {d}
                         if owner in above[t]}))


def _shared(types: list[SymbolInfo]) -> set[str]:
    ids: dict[str, set[str]] = defaultdict(set)
    for t in types:
        ids[t.qualified_name].add(t.id)
    return {q for q, found in ids.items() if len(found) > 1}


def _ancestors(up: dict[str, set[str]], type_id: str) -> set[str]:
    seen, todo = set(), list(up.get(type_id, ()))
    while todo:
        t = todo.pop()
        if t not in seen:
            seen.add(t)
            todo += up.get(t, ())
    return seen


def _kind(source: SymbolInfo, target: SymbolInfo) -> str:
    return "IMPLEMENTS" if target.kind == "interface" and source.kind != "interface" else "EXTENDS"
