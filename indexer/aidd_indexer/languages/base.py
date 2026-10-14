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

from ..core.dispatch import DispatchRule

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
    facts: dict[str, dict[str, Any]] = field(default_factory=dict)   # file id -> `file_facts()` of its language
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
    parent_receivers: frozenset[str] = frozenset()   # keywords naming the base type (C# `base`): if it is not in the repo, don't guess
    ecosystem: str = ""                            # go | npm | pypi | nuget (external Package nodes)
    http_scanner: "type[BaseScanner] | None" = None
    namespace_nodes: frozenset[str] = frozenset()  # tree node types that prefix qualified names (C# namespaces)
    entry_point_hints: tuple[str, ...] = ()        # substrings of the signature that mark an entry point
    decorator_entry: re.Pattern | None = None      # regex over leading decorators/attributes
    dispatch: tuple[DispatchRule, ...] = ()         # mediators of public libraries (MediatR), always on; an organization's
                                                   # own bus is declared by its convention (`dispatch:`, core/dispatch.py)

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

    def def_node(self, node: Node) -> Node:
        """The node a definition is recorded on (signature, doc, lines) — by default the one the
        query captured. Go records a lone spec on its declaration (`type X struct`)."""
        return node

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

    def file_facts(self, root: Node, src: bytes) -> dict[str, Any]:
        """Per-file facts the resolver may need later (Go: struct field types, import aliases,
        constructor return types). Stored on the extractor and handed to `resolve_receiver` via ctx.facts."""
        return {}

    def call_receiver(self, call: Node, receiver: Node, src: bytes) -> tuple[str, tuple[str, ...]] | None:
        """(static type of the receiver's base variable as written, field path) for `x.y.Method()`,
        when the enclosing function declares it (receiver, parameter, typed local). None = unknown."""
        return None

    def call_argument_type(self, call: Node, src: bytes) -> str | None:
        """Static type of the call's first argument as written — `new T(..)`, or a parameter/local
        (preferring the type it was created with over the declared one: `IEvent e = new T()` → T).
        Asked only for the bus methods of a convention's `dispatch` rules. None = unknown."""
        return None

    # ---- manifests -----------------------------------------------------------------
    def manifest_deps(self, rel_path: str, text: str) -> tuple[list[str], list[tuple[str, str]]]:
        """(names this manifest publishes, [(required package name, version)]) for a manifest of
        this language (`manifests` / `manifest_suffixes`). Names come back raw — `core/deps.py`
        normalizes them. Only direct dependencies: the linker turns a requirement whose name another
        repo of the tenant publishes into `Service -[:DEPENDS_ON]-> Service`."""
        return [], []

    # ---- resolution ---------------------------------------------------------------------
    def resolve_setup(self, ctx: ResolveContext) -> None:
        """Compute per-repo lookups once (Go: module paths from go.mod) into `ctx.extra`."""
        return None

    def resolve_import(self, ctx: ResolveContext, file: "FileInfo", spec: str, pkg: PackageFactory) -> tuple[str, str] | None:
        """(target id, label) for an import spec, `label` in File | Module | Package; None = unresolved."""
        return None

    def resolve_receiver(self, ctx: ResolveContext, file: "FileInfo", receiver_type: str, path: tuple[str, ...]) -> str | None:
        """Qualified type name (`internal.domain.password.Policy`) of a call receiver, following
        `path` through struct fields; None when it cannot be determined. Lets `resolve.py` pick the
        method of *that* type among homonyms (strategy `receiver-type`)."""
        return None

    def supertypes(self, ctx: ResolveContext, qualified_type: str) -> list[str]:
        """Qualified names of the in-repo base types of a type (nearest first), so a method inherited
        from a base class declared in this repo still resolves by receiver type."""
        return []

    def implementation_target(self, ctx: ResolveContext, qualified_type: str, method: str) -> str | None:
        """Qualified name of the single concrete type that implements `qualified_type` *and* can
        serve `method` for it — None when there are zero or several implementers, or when the
        implementer's `method` is an explicit implementation of another interface. A call on the
        interface then also links to the implementation (strategy `receiver-type-impl`), the usual
        DI case in C#."""
        return None

    def message_handlers(self, ctx: ResolveContext, file: "FileInfo", message_type: str,
                         handler_bases: frozenset[str]) -> list[str]:
        """Qualified names of the types whose base list has one of `handler_bases` with `message_type`
        (as seen from `file`) as its first type argument — who receives a message sent through a
        mediator (core/dispatch.py). Empty when the language has no generics or none matches."""
        return []

    def link_symbols(self, symbols: list["SymbolInfo"], files_by_id: dict[str, "FileInfo"]) -> None:
        """Repo-wide post-processing (Go: methods → receiver struct as parent)."""
        return None
