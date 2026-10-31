"""`CALLS` and `IMPORTS` inside one repo. A mediator's call goes to the message's handlers; another, to the method of
its receiver's static type or where that type leads (its implementation, a base outside the repo, a C# extension
method); with no type, to the callee's homonyms, narrowed same-file → same-module → repo-unique. A call the language
sends to one method by name (`base.M()`, `super().m()`) reaches no implementation, and with no type only the classes
the language names. An import goes where the file's `LanguageSupport.resolve_import` maps the spec: a File, a Module or
an external `Package`. A type's bases of the repo are `EXTENDS` and `IMPLEMENTS`, and a method a dispatching call
may run instead of another `OVERRIDES` it (core/hierarchy.py)."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .. import languages
from ..languages.base import ResolveContext
from . import ids
from .config import is_test_path
from .dispatch import DispatchRule
from .edges import CallEdge, ImportEdge, PackageNode, one_per_edge
from .extract import CALLABLE_KINDS, FileExtractor
from .hierarchy import HierarchyEdge, override_edges, type_edges
from .model import ExtractionResult, FileInfo, SymbolInfo
from .nearest import fits, fitting, nearest, pruned

TYPE_KINDS = frozenset({"class", "interface", "struct", "record", "type"})

# receivers that are runtime builtins in some language — a call on them never targets repo code
BUILTIN_RECEIVERS: frozenset[str] = frozenset().union(*(l.builtin_receivers for l in languages.all()))


@dataclass
class Resolved:
    calls: list[CallEdge]
    imports: list[ImportEdge]
    packages: dict[str, PackageNode]
    unresolved_calls: int
    unresolved_imports: int
    # declared namespace -> declaring file ids (C#). Not written to the graph: an import of a namespace
    # targets its Module, and conventions use this to see which files (hence which layer) it reaches.
    namespace_files: dict[str, list[str]] = field(default_factory=dict)
    hierarchy: list[HierarchyEdge] = field(default_factory=list)


class Resolver:
    def __init__(self, result: ExtractionResult, extractors: list[FileExtractor], dispatch: list[DispatchRule] | None = None):
        self.r = result
        self.dispatch = dispatch or []
        self.root = Path(result.repo.root)
        self.files_by_path = {f.path: f for f in result.files}
        self.files_by_id = {f.id: f for f in result.files}
        self.modules_by_path = {m.path: m for m in result.modules}
        self.module_by_id = {m.id: m for m in result.modules}
        self.by_name: dict[str, list[SymbolInfo]] = defaultdict(list)
        for s in result.symbols:
            if s.kind in CALLABLE_KINDS:
                self.by_name[s.name].append(s)
        self.sym_by_id = {s.id: s for s in result.symbols}
        self.type_by_q = {s.qualified_name: s for s in result.symbols if s.kind in TYPE_KINDS}
        namespaces: dict[str, list[str]] = defaultdict(list)
        for fx in extractors:
            for ns in fx.namespaces:
                namespaces[ns].append(fx.file.id)
        self.packages: dict[str, PackageNode] = {}
        self.external_bindings: dict[str, set[str]] = defaultdict(set)   # file id -> names bound to external packages
        self.ctx = ResolveContext(self.root, self.files_by_path, self.modules_by_path, self.module_by_id, self.files_by_id,
                                  dict(namespaces), facts={fx.file.id: fx.facts for fx in extractors}, types=result.types)
        self.test_file = {f.id: is_test_path(f.path) for f in result.files}
        for lang in languages.all():
            lang.resolve_setup(self.ctx)

    # -- calls -----------------------------------------------------------------------
    def resolve_calls(self) -> tuple[list[CallEdge], int]:
        edges: list[CallEdge] = []
        unresolved = 0
        for c in self.r.calls:
            if c.arg_type:                       # a bus method of a convention's `dispatch`: link to the handlers
                sent = self._dispatched(c)
                if sent:
                    edges.extend(sent)
                    continue
            cands = self.by_name.get(c.callee_name, [])
            if not cands and not c.receiver_type:   # typed receivers go on: the method may come from a package base
                unresolved += 1
                continue
            if c.receiver:
                root = re.split(r"[.(\[]", c.receiver, 1)[0].strip()
                if root in BUILTIN_RECEIVERS or root in self.external_bindings.get(c.file_id, ()):
                    unresolved += 1          # call into an external package / runtime builtin
                    continue
            caller_file = self.files_by_id.get(c.file_id)
            # production code never targets test code: drop fakes/mocks from the candidate set
            if not self.test_file.get(c.file_id, False):
                prod = [s for s in cands if not self.test_file.get(s.file_id, False)]
                if not prod and not c.receiver_type:
                    unresolved += 1
                    continue
                cands = prod
            # static receiver type (Go: struct field / parameter / constructor) picks the method among homonyms
            if c.receiver_type and caller_file is not None:
                lang = languages.by_id(caller_file.language)
                qtype = lang.resolve_receiver(self.ctx, caller_file, c.receiver_type, c.receiver_path) if lang else None
                typed = self._typed(c, cands, qtype, lang) if qtype else None
                if typed is not None:
                    edges.extend(typed[0])
                    unresolved += typed[1]
                    continue
            fit = None                       # how each extension takes the receiver, when only extensions can serve it
            if c.receiver and caller_file is not None:
                # a receiver whose type is a package's (`Substitute.For<T>()`, `fixture.Build<T>()`, `_logger.LogX()`),
                # or a generic method on a receiver of unknown type (`builder.Services.Configure<T>()`): only the
                # repo's extension methods can be the target — a homonym found by name is not
                lang = languages.by_id(caller_file.language)
                package, ends = (lang.external_receiver(self.ctx, caller_file, c.receiver_type, c.receiver_path)
                                 if lang is not None and c.receiver_type else None) or (None, False)
                if lang is not None and (package or c.generic):
                    # an extension needs an instance (`Assert.Contains(..)` is the static class's own) and must take
                    # the arguments: the type's own method wins over it (`list.Contains(x)` is `List`'s)
                    static = package is not None and c.receiver == package and not c.receiver_path
                    fit = {} if static else {s.id: lang.extension_fit(self.ctx, s, package, ends, c.generic)
                                             for s in cands if fits(s, c.arg_count)}
                    cands = [s for s in cands if fit.get(s.id)]
            if not cands:
                unresolved += 1
                continue
            lang = languages.by_id(caller_file.language) if caller_file is not None else None
            if lang is not None and not lang.dispatches(c):   # a homonym found by name may be the override itself
                sent = self._named_after(c, caller_file, cands, lang)
                edges.extend(sent)
                unresolved += not sent
                continue
            mod = caller_file.module_id if caller_file else None
            picked = nearest(c, cands, self.files_by_id, mod) if fit is None \
                else pruned(lambda found: nearest(c, found, self.files_by_id, mod), cands, fit)
            if not picked:
                unresolved += 1
            edges.extend(self._edge(c, s.id, strat) for s, strat in picked)
        return one_per_edge(edges), unresolved

    def _edge(self, c, callee_id: str, strategy: str, method: str | None = None) -> CallEdge:
        f = self.files_by_id.get(c.file_id)
        lang = languages.by_id(f.language) if f is not None else None
        return CallEdge(c.caller_id, callee_id, c.line, strategy, method, lang is None or lang.dispatches(c))

    def _named_after(self, c, file: FileInfo, cands: list[SymbolInfo], lang) -> list[CallEdge]:
        """A call the language sends to one method by name, its receiver's type not telling which: the methods of the
        classes the language names (`LanguageSupport.declaring_after`)."""
        hits = [s for t in lang.declaring_after(self.ctx, file, c) for s in cands
                if s.qualified_name == lang.member_name(t, c.callee_name)]
        strategy = "receiver-type" + ("-ambiguous" if len(hits) > 1 else "")
        return [self._edge(c, s.id, strategy) for s in hits]

    def _typed(self, c, cands: list[SymbolInfo], qtype: str, lang) -> tuple[list[CallEdge], int] | None:
        """The edges the receiver's type gives a call, and 1 when it gives none; None when the call goes by name, its
        type declaring no such method that the language lets another class give (`LanguageSupport.member_by_name`)."""
        found = self._on_type(c, cands, qtype, lang)
        # overloads the argument count cannot tell apart: all of them, marked ambiguous
        edges = [self._edge(c, s.id, strategy + ("-ambiguous" if len(hits) > 1 else ""))
                 for hits, strategy in found for s in hits[:3]]
        if found[0][0]:
            return edges, 0
        # the receiver's type does not declare the method: never guess a homonym. When the type has a base outside the
        # repo the method comes from there — record the dependency on the type
        inherited = self._inherited(c, qtype, lang, impl_found=bool(found[-1][0]))
        if found[-1][0] or inherited:
            return edges + inherited, 0
        return None if lang.member_by_name(self.ctx, qtype, c.callee_name) else (edges, 1)

    def _on_type(self, c, cands: list[SymbolInfo], qtype: str, lang) -> list[tuple[list[SymbolInfo], str]]:
        """The methods of the receiver's type and of the implementation it reaches; when none takes the arguments, the
        repo's methods the language calls on the receiver (C# extension methods)."""
        typed = self._methods_on(cands, c.callee_name, qtype, lang, c.arg_count)
        impl = lang.implementation_target(self.ctx, qtype, c.callee_name, self._owner(c.caller_id)) \
            if lang.dispatches(c) else None
        impl_typed = self._methods_on(cands, c.callee_name, impl, lang, c.arg_count) if impl else []
        found = [(typed, "receiver-type"), (impl_typed, "receiver-type-impl")]
        if any(fits(s, c.arg_count) for s in typed + impl_typed):
            return found
        return lang.extension_methods(self.ctx, [s for s in cands if fits(s, c.arg_count)], qtype,
                                      "" if c.receiver_path else c.receiver_type) or found

    def _inherited(self, c, qtype: str, lang, impl_found: bool = False) -> list[CallEdge]:
        """`repo.CreateAsync(x)` where `repo: ITodoRepository : IBaseRepository<T>` (a package): CALLS to the
        type itself and to its single implementer, carrying the method name (strategies `inherited` /
        `inherited-impl`) — who uses this repository stays visible without inventing the method."""
        if not lang.has_external_base(self.ctx, qtype):
            return []
        owners = {qtype, *lang.supertypes(self.ctx, qtype)}
        if any(s.qualified_name.rsplit(".", 1)[0] in owners for s in self.by_name.get(c.callee_name, [])):
            return []                    # declared in the repo (overloads: no single target) — not a package method
        caller_test = self.test_file.get(c.file_id, False)
        out = []
        impl = None if impl_found or not lang.dispatches(c) \
            else lang.implementation_target(self.ctx, qtype, c.callee_name, self._owner(c.caller_id))
        for target, strategy in ((qtype, "inherited"), (impl, "inherited-impl")):
            t = self.type_by_q.get(target) if target else None
            if t is None or self._inside(c.caller_id, t.id) or (not caller_test and self.test_file.get(t.file_id, False)):
                continue                 # its own type (`this.ResponseAsync()` in a controller) says nothing new
            out.append(self._edge(c, t.id, strategy, c.callee_name))
        return out

    def _owner(self, symbol_id: str) -> str | None:
        """Qualified name of the type a symbol is declared in (the caller's own type), if any."""
        s = self.sym_by_id.get(symbol_id)
        while s is not None and s.kind not in TYPE_KINDS:
            s = self.sym_by_id.get(s.parent_id) if s.parent_id else None
        return s.qualified_name if s is not None else None

    def _inside(self, symbol_id: str, type_id: str) -> bool:
        s = self.sym_by_id.get(symbol_id)
        while s is not None:
            if s.id == type_id:
                return True
            s = self.sym_by_id.get(s.parent_id) if s.parent_id else None
        return False

    def _dispatched(self, c) -> list[CallEdge]:
        """`bus.SendAsync(new X(..))` → `Handle` of every type that handles X (core/dispatch.py)."""
        f = self.files_by_id.get(c.file_id)
        lang = languages.by_id(f.language) if f is not None else None
        if lang is None:
            return []
        out: dict[str, CallEdge] = {}
        for rule in [*self.dispatch, *lang.dispatch]:          # the conventions' bus, then the language's (MediatR)
            if c.callee_name not in rule.calls:
                continue
            for handler in lang.message_handlers(self.ctx, f, c.arg_type, rule.handlers):
                hit = self._methods_on(self.by_name.get(rule.method, []), rule.method, handler, lang)
                target = hit[0] if len(hit) == 1 else None
                if target is not None and (self.test_file.get(c.file_id, False) or not self.test_file.get(target.file_id, False)):
                    out.setdefault(target.id, self._edge(c, target.id, "dispatch"))
        return list(out.values())

    def _methods_on(self, cands: list[SymbolInfo], name: str, qtype: str, lang, argc: int | None = None) -> list[SymbolInfo]:
        """The method declared on `qtype` or, failing that, on its nearest in-repo supertype — the overloads that
        accept `argc` arguments (all of them when none does: the arity read may be incomplete)."""
        for t in [qtype] + lang.supertypes(self.ctx, qtype):
            hit = [s for s in cands if s.qualified_name == lang.member_name(t, name)]
            if hit:
                return fitting(hit, argc)
        return []

    # -- imports ---------------------------------------------------------------------
    def _pkg(self, ecosystem: str, name: str, stdlib: bool = False) -> str:
        """Package factory handed to language modules — returns the node id."""
        pid = ids.package(self.r.repo.tenant, ecosystem, name)
        if pid not in self.packages:
            self.packages[pid] = PackageNode(pid, name, ecosystem, stdlib)
        return pid

    def resolve_imports(self) -> tuple[list[ImportEdge], int]:
        edges: list[ImportEdge] = []
        unresolved = 0
        for imp in self.r.imports:
            f = self.files_by_id.get(imp.file_id)
            if f is None:
                continue
            target = self._resolve_one(f, imp.spec)
            if target is None:
                unresolved += 1
                continue
            tid, label = target
            if label == "Package":
                self.external_bindings[imp.file_id].update(imp.bindings)
            edges.append(ImportEdge(imp.file_id, tid, label, imp.line, imp.spec))
        return edges, unresolved

    def _resolve_one(self, f: FileInfo, spec: str) -> tuple[str, str] | None:
        lang = languages.by_id(f.language)
        return lang.resolve_import(self.ctx, f, spec, self._pkg) if lang is not None else None

    def run(self) -> Resolved:
        for lang in languages.all():             # repo-wide fixups (Go: methods → receiver struct)
            lang.link_symbols(self.r.symbols, self.files_by_id)
        imports, ui = self.resolve_imports()      # first: populates external_bindings
        calls, uc = self.resolve_calls()
        types = [s for s in self.r.symbols if s.kind in TYPE_KINDS]
        bases = type_edges(types, self.files_by_id, self.ctx)
        methods = [s for s in self.r.symbols if s.kind == "method"]
        return Resolved(calls, imports, self.packages, uc, ui, self.ctx.namespaces,
                        sorted(bases + override_edges(types, methods, bases, self.files_by_id, self.ctx)))
