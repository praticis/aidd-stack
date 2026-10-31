"""`EXTENDS` and `IMPLEMENTS` inside one repo: the types of the repo a type names as its direct bases, as its language
reads them (`LanguageSupport.bases`). A type that is not an interface implements an interface it names, and extends
any other base. A base declared in parts (a C# partial type) is each of its declarations. Two types of one qualified
name (C#'s `IFoo` and `IFoo<T>` in one file) are told apart by no name a base writes: neither has an edge."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .. import languages
from ..languages.base import ResolveContext
from .model import FileInfo, SymbolInfo


@dataclass(frozen=True, order=True)
class TypeEdge:
    source_id: str
    target_id: str
    kind: str                       # EXTENDS | IMPLEMENTS


def type_edges(types: list[SymbolInfo], files_by_id: dict[str, FileInfo], ctx: ResolveContext) -> list[TypeEdge]:
    """The edges from each of `types` to the declarations of its bases, sorted."""
    declared: dict[str, list[SymbolInfo]] = defaultdict(list)
    for t in types:
        declared[t.qualified_name].append(t)
    shared = {q for q, found in declared.items() if len({t.id for t in found}) > 1}
    read: dict[tuple[str, str], list[str]] = {}     # a partial type's parts ask once
    edges = set()
    for t in (t for t in types if t.qualified_name not in shared):
        language = files_by_id[t.file_id].language
        if (language, t.qualified_name) not in read:
            support = languages.by_id(language)
            read[language, t.qualified_name] = support.bases(ctx, t.qualified_name) if support is not None else []
        edges |= {TypeEdge(t.id, b.id, _kind(t, b)) for q in read[language, t.qualified_name] if q not in shared
                  for b in declared.get(q, ()) if b.id != t.id}
    return sorted(edges)


def _kind(source: SymbolInfo, target: SymbolInfo) -> str:
    return "IMPLEMENTS" if target.kind == "interface" and source.kind != "interface" else "EXTENDS"
