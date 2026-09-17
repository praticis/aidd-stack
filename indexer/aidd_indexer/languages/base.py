"""The contract every language module implements (ADR-003).

`core/` never asks "which language is this?" — it asks the registry for the `LanguageSupport`
of a file and calls these hooks. A new language = a folder under `languages/` with a subclass,
a `queries.scm`, and one line in `languages/__init__.py`. Every hook has a sensible default so a
module only overrides what its language needs.

Hook groups:

* **identity** — id, grammar, extensions, query file, stack tag, manifests, builtin receivers;
* **discovery** — extra modules a language implies (Go: every directory with .go files);
* **symbols** — qualified names, kinds, visibility, docs, entry points and import bindings
  derived from the tree (`core/extract.py` calls them per file);
* **resolution** — how an import spec maps to a File/Module/Package, plus repo-wide
  post-processing of symbols (`core/resolve.py` calls them per repo);
* **http** — the `BaseScanner` subclass that finds routes exposed and outbound calls
  (`core/integrations.py`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Callable

from tree_sitter import Node

if TYPE_CHECKING:  # pragma: no cover
    from ..core.http_base import BaseScanner
    from ..core.model import FileInfo, ModuleInfo, RepoInfo, SymbolInfo


def node_text(node: Node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def walk(node: Node):
    """Pre-order traversal."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


@dataclass
class ResolveContext:
    """What `resolve_import` may look at (a read-only view of the Resolver)."""
    root: Path
    files_by_path: dict[str, "FileInfo"]
    modules_by_path: dict[str, "ModuleInfo"]
    module_by_id: dict[str, "ModuleInfo"]
    files_by_id: dict[str, "FileInfo"]
    namespaces: dict[str, list[str]]           # declared namespace -> declaring file ids (from `file_scope`)
    extra: dict[str, Any] = field(default_factory=dict)   # per-language scratch filled by `resolve_setup`

    def file_at(self, rel: str) -> "FileInfo | None":
        return self.files_by_path.get(rel)


# `pkg(ecosystem, name, stdlib) -> package id` — creates the external Package node on demand.
PackageFactory = Callable[[str, str, bool], str]


@dataclass
class LanguageSupport:
    """Defaults are the generic behaviour; subclasses override per language."""

    id: str
    grammar: str                                   # name in tree-sitter-language-pack
    extensions: tuple[str, ...]                    # ".go"
    query_file: Path                               # languages/<lang>/queries.scm
    stack: str = ""                                # what Repo.stack shows when a manifest is found: go | ts | dotnet | python
    manifests: dict[str, str] = field(default_factory=dict)          # "go.mod" -> "go-module"
    manifest_suffixes: dict[str, str] = field(default_factory=dict)  # ".csproj" -> "csproj"
    builtin_receivers: frozenset[str] = frozenset()  # `console.log`, `Task.Run` — calls into the runtime, never resolved
    ecosystem: str = ""                            # go | npm | pypi | nuget (external Package nodes)
    http_scanner: "type[BaseScanner] | None" = None
    namespace_nodes: frozenset[str] = frozenset()  # tree node types that prefix qualified names (C# namespaces)
    entry_point_hints: tuple[str, ...] = ()        # substrings of the signature that mark an entry point
    decorator_entry: re.Pattern | None = None      # regex over leading decorators/attributes

    # ---- discovery ------------------------------------------------------------------------
    def discover_modules(self, repo: "RepoInfo", rel_files: list[str], modules: dict[str, "ModuleInfo"]) -> None:
        """Add language-implied modules to `modules` (keyed by directory). Default: none."""
        return None

    # ---- symbols ------------------------------------------------------------------------
    def module_prefix(self, file: "FileInfo") -> str:
        """Scope prefix for qualified names. Default: file path without extension."""
        return str(PurePosixPath(file.path).with_suffix(""))

    def qualified_name(self, prefix: str, chain: list[str], name: str) -> str:
        """Default `module/path:Class.method`."""
        return (prefix + ":" if prefix else "") + ".".join(chain + [name])

    def adjust_kind(self, kind: str, parent: "SymbolInfo | None") -> str:
        return kind

    def scope_chain(self, dnode: Node, src: bytes, chain: list[str], kind: str, file_namespace: str | None) -> list[str]:
        """Chance to replace the syntactic scope (Go receivers, C# file-scoped namespaces)."""
        return chain

    def visibility(self, name: str, node: Node, src: bytes, first_line: str) -> str:
        if re.search(r"\b(private|protected|internal)\b", first_line):
            return "private"
        if re.search(r"\b(public|export)\b", first_line):
            return "public"
        if node.parent is not None and node.parent.type == "export_statement":
            return "public"
        return "unknown"

    def doc_extra(self, node: Node, src: bytes) -> list[str]:
        """Documentation that is not a leading comment (Python docstrings)."""
        return []

    def import_bindings(self, stmt_text: str, stmt: Node, spec: str, src: bytes) -> list[str]:
        """Local names an import statement introduces (`import axios from 'axios'` → ['axios'])."""
        return []

    def file_scope(self, root: Node, src: bytes) -> tuple[list[str], str | None]:
        """(namespaces declared in the file, file-scoped namespace) — C# only for now."""
        return [], None

    # ---- resolution ---------------------------------------------------------------------
    def resolve_setup(self, ctx: ResolveContext) -> None:
        """Compute per-repo lookups once (Go: module paths from go.mod) into `ctx.extra`."""
        return None

    def resolve_import(self, ctx: ResolveContext, file: "FileInfo", spec: str, pkg: PackageFactory) -> tuple[str, str] | None:
        """(target id, label) for an import spec, `label` in File | Module | Package; None = unresolved."""
        return None

    def link_symbols(self, symbols: list["SymbolInfo"], files_by_id: dict[str, "FileInfo"]) -> None:
        """Repo-wide post-processing (Go: methods → receiver struct as parent)."""
        return None
