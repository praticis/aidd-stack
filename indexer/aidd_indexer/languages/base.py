"""The contract every language module implements.

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
from ..tree import node_text, walk  # noqa: F401  the language modules import them from here

if TYPE_CHECKING:  # pragma: no cover
    from ..core.hierarchy import Declared
    from ..core.http_base import BaseScanner
    from ..core.model import CallInfo, FileInfo, ModuleInfo, RepoInfo, SymbolInfo
    from ..core.types import Unknown


@dataclass
class ResolveContext:
    """What `resolve_import` may look at (a read-only view of the Resolver)."""
    root: Path
    files_by_path: dict[str, "FileInfo"]
    modules_by_path: dict[str, "ModuleInfo"]
    module_by_id: dict[str, "ModuleInfo"]
    files_by_id: dict[str, "FileInfo"]
    namespaces: dict[str, list[str]]           # declared namespace -> declaring file ids (from `file_scope`)
    facts: dict[str, Any] = field(default_factory=dict)   # file id -> `file_facts()` of its language
    extra: dict[str, Any] = field(default_factory=dict)   # per-language scratch filled by `resolve_setup`
    types: Any = None                          # the repo's type service, shared with the HTTP pass (`RepoTypes`)

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
    type_family: str = ""                          # languages whose files share one `TypeIndex` (TS's three); "" for its own
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

    def package_facts(self, src: bytes) -> "Callable[[Node, bytes, Any, str], bool] | None":
        """A reader of the language's own facts of a package (`PackageContext`), made per file. The constants pass
        calls it on each node of the file first and skips the node when it answers True. None: the language has
        none."""
        return None

    def file_index(self, root: Node, src: bytes) -> Any:
        """The file's own index, built once before the hooks that read one file and handed to them (Python: what each
        name refers to). It may hold the tree's nodes, so it lives only while the file is extracted, never in the
        facts. None: the language reads the tree at each question."""
        return None

    def file_facts(self, root: Node, src: bytes, index: Any = None) -> Any:
        """Per-file type facts the resolver and the scanners read across files, holding no tree node (Go: `GoTypes`).
        Stored on the extractor and handed to `resolve_receiver` via ctx.facts."""
        return {}

    def call_receiver(self, call: Node, receiver: Node, src: bytes,
                      index: Any = None) -> "tuple[str, tuple[str, ...]] | Unknown | None":
        """(static type of the receiver's base variable as written, field path) for `x.y.Method()`,
        when the enclosing function declares it (receiver, parameter, typed local); `Unknown` with its reason when
        the declarations in sight do not decide it. None = unknown."""
        return None

    def arity(self, node: Node, src: bytes) -> tuple[int, int | None] | None:
        """(required, max) arguments a call to this function/method passes — optional parameters and
        defaults widen the range, a variadic one makes max None. None = unknown (no overload filtering)."""
        return None

    def call_arg_count(self, call: Node, src: bytes) -> int | None:
        """How many arguments the call passes; None when unknown (a spread)."""
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

    def type_index(self, ctx: ResolveContext) -> Any:
        """The language's answers to the type service's questions (a `core.types.TypeIndex`), built from every file's
        type facts in `ctx`; None for a language that answers none."""
        return None

    def resolve_import(self, ctx: ResolveContext, file: "FileInfo", spec: str, pkg: PackageFactory) -> tuple[str, str] | None:
        """(target id, label) for an import spec, `label` in File | Module | Package; None = unresolved."""
        return None

    def resolve_receiver(self, ctx: ResolveContext, file: "FileInfo", receiver_type: str, path: tuple[str, ...]) -> str | None:
        """Qualified type name (`internal.domain.password.Policy`) of a call receiver, following
        `path` through struct fields; None when it cannot be determined. Lets `resolve.py` pick the
        method of *that* type among homonyms (strategy `receiver-type`)."""
        return None

    def external_receiver(self, ctx: ResolveContext, file: "FileInfo", receiver_type: str,
                          path: tuple[str, ...]) -> tuple[str, bool] | None:
        """A type the receiver's chain reaches that is named in the code and declared outside the repo
        (`Substitute.For<T>()`, a `Fixture fixture`, an `ILogger _logger`), and whether the chain ends in it: a method
        on it is the package's, so the resolver does not guess a homonym of the repo by name — except an extension
        method (`extension_fit`). None otherwise."""
        return None

    def extension_fit(self, ctx: ResolveContext, symbol: "SymbolInfo", package: str | None = None, ends: bool = False,
                      generic: bool = False) -> str | None:
        """How a method of the repo callable on a type declared elsewhere (C# `static X M(this T x)`) takes a call's
        receiver of type `package` (the chain `ends` in it, or only passes through it), or of unknown type; `generic`:
        the call is written with type arguments. "compatible" when it takes it, "incompatible" when the language
        proves it cannot, "unknown" when it may; None when it is no such method or is not considered."""
        return None

    def extension_methods(self, ctx: ResolveContext, symbols: list["SymbolInfo"], qualified_type: str,
                          written: str = "") -> list[tuple[list["SymbolInfo"], str]]:
        """Among `symbols`, the methods of the repo a call on a value of the repo's `qualified_type` reaches when no
        method of the type takes its arguments (C# extension methods), with the strategy that found them. `written`:
        the receiver's type as `call_receiver` wrote it, when no member follows it: it tells a value from a type's
        name."""
        return []

    def bases(self, ctx: ResolveContext, qualified_type: str) -> list[str]:
        """Qualified names of the types of the repo a type names as its direct bases, where a call on the type may run
        a base's method or an override of it (`EXTENDS`, `IMPLEMENTS`). A base the language cannot find in the repo is
        left out. Go embeds a type, which promotes its methods and dispatches none: no base."""
        return []

    def dispatches(self, call: "CallInfo") -> bool:
        """Whether the class of the object the call is made on may choose the method it runs: not where the language
        sends the call to a base's method by name (C# `base.M()`, Python `super().m()`)."""
        return True

    def declaring_after(self, ctx: ResolveContext, file: "FileInfo", call: "CallInfo") -> list[str]:
        """For a call that does not dispatch, whose receiver's type does not tell which method it runs (Python
        `super()` in a class of several bases): the qualified names of the classes whose method it may run. None by
        default: C#'s `base` is typed by the class's base, or that base is outside the repo."""
        return []

    def dispatched(self, ctx: ResolveContext, declared: "Declared", instance: str,
                   method: "SymbolInfo") -> list["SymbolInfo"]:
        """The methods a dispatching call to `method` may run on an instance of the type `instance`, at or below the
        method's type: the method itself, the one that overrides or implements it, or each of several the language cannot
        tell apart. None where the language cannot tell, and by default."""
        return []

    def supertypes(self, ctx: ResolveContext, qualified_type: str) -> list[str]:
        """Qualified names of the in-repo base types of a type (nearest first), so a method inherited
        from a base class declared in this repo still resolves by receiver type."""
        return []

    def member_name(self, owner: str, name: str) -> str:
        """Qualified name of the member `name` of `owner`, a type `resolve_receiver` answers. A language whose modules
        are namespaces too (Python: `path:function` beside `path:Class.method`) tells them apart here."""
        return f"{owner}.{name}"

    def member_by_name(self, ctx: ResolveContext, qualified_type: str, name: str) -> bool:
        """Whether a call of a method the type declares nowhere, and no base outside the repo may give, still reaches
        one of the repo's at run time, so it goes by name: where another class may give it. Never in a language that
        checks a call against its receiver's type."""
        return False

    def has_external_base(self, ctx: ResolveContext, qualified_type: str) -> bool:
        """Whether the type (or one of its in-repo bases) extends/embeds a type declared outside the repo —
        so a method the repo does not declare may come from there (`ITodoRepository : IBaseRepository<T>`
        of a package). Lets the resolver keep the dependency on the type (strategy `inherited`)."""
        return False

    def implementation_target(self, ctx: ResolveContext, qualified_type: str, method: str,
                              from_type: str | None = None) -> str | None:
        """Qualified name of the concrete type a call on `qualified_type` reaches — the single implementer, or
        the one the DI registrations say (C#: `AddScoped<I, Impl>()`, and a `Decorate<I, D>()` chain, where
        `from_type` — the caller's own type — picks the next one inward) — and that can serve `method` for
        it. None when it cannot be told, or when the implementer's `method` is an explicit implementation
        of another interface. A call on the interface then also links to the implementation (strategy
        `receiver-type-impl`)."""
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
