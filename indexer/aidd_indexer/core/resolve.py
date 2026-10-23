"""`CALLS` and `IMPORTS` inside one repo. A mediator's call goes to the message's handlers; another, to the method of
its receiver's static type or where that type leads (its implementation, a base outside the repo, a C# extension
method); with no type, to the callee's homonyms, narrowed same-file → same-module → repo-unique. An import goes where
the file's `LanguageSupport.resolve_import` maps the spec: a File, a Module or an external `Package`."""

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
from .extract import CALLABLE_KINDS, FileExtractor
from .model import ExtractionResult, FileInfo, SymbolInfo

TYPE_KINDS = frozenset({"class", "interface", "struct", "record", "type"})

# receivers that are runtime builtins in some language — a call on them never targets repo code
BUILTIN_RECEIVERS: frozenset[str] = frozenset().union(*(l.builtin_receivers for l in languages.all()))


@dataclass
class CallEdge:
    caller_id: str
    callee_id: str
    line: int
    strategy: str          # receiver-type | receiver-type-impl | dispatch | inherited | inherited-impl | same-file | same-module | unique-name (+ "-ambiguous")
    method: str | None = None   # inherited*: the method called, which the repo does not declare (it comes from a package base)


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


def _fitting(syms: list[SymbolInfo], argc: int | None) -> list[SymbolInfo]:
    """The symbols a call with `argc` arguments can reach (overloads by arity); unchanged when the count or the
    arities are unknown, or when none fits."""
    return [s for s in syms if _fits(s, argc)] or syms if len(syms) > 1 else syms


def _fits(s: SymbolInfo, argc: int | None) -> bool:
    return argc is None or s.arity is None or (s.arity[0] <= argc and (s.arity[1] is None or argc <= s.arity[1]))


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
                if qtype:
                    found = self._on_type(c, cands, qtype, lang)
                    for hits, strategy in found:
                        # overloads the argument count cannot tell apart: all of them, marked ambiguous
                        suffix = "-ambiguous" if len(hits) > 1 else ""
                        edges.extend(CallEdge(c.caller_id, s.id, c.line, strategy + suffix) for s in hits[:3])
                    if not found[0][0]:
                        # the receiver's type does not declare the method: never guess a homonym. When the type has a
                        # base outside the repo the method comes from there — record the dependency on the type
                        inherited = self._inherited(c, qtype, lang, impl_found=bool(found[-1][0]))
                        edges.extend(inherited)
                        if not found[-1][0] and not inherited:
                            unresolved += 1
                    continue
            if c.receiver and caller_file is not None:
                # a receiver whose type is a package's (`Substitute.For<T>()`, `fixture.Build<T>()`, `_logger.LogX()`),
                # or a generic method on a receiver of unknown type (`builder.Services.Configure<T>()`): only the
                # repo's extension methods can be the target — a homonym found by name is not
                lang = languages.by_id(caller_file.language)
                package = lang.external_receiver(self.ctx, caller_file, c.receiver_type, c.receiver_path) \
                    if lang is not None and c.receiver_type else None
                if lang is not None and (package or c.generic):
                    # an extension needs an instance (`Assert.Contains(..)` is the static class's own) and must take
                    # the arguments: the type's own method wins over it (`list.Contains(x)` is `List`'s)
                    static = package is not None and c.receiver == package and not c.receiver_path
                    cands = [] if static else [s for s in cands if lang.is_extension_method(self.ctx, s, package, unknown=not package)
                                                and _fits(s, c.arg_count)]
                    if not cands:
                        unresolved += 1
                        continue
            if not cands:
                unresolved += 1
                continue
            lang = languages.by_id(caller_file.language) if caller_file is not None else None
            if c.receiver and lang is not None and c.receiver in lang.parent_receivers:
                unresolved += 1              # `base.X()` with the base type outside the repo (or implicit): the name fallback would only find the override itself
                continue
            same_file = [s for s in cands if s.file_id == c.file_id]
            if same_file:
                chosen, strat = same_file, "same-file"
            else:
                mod = caller_file.module_id if caller_file else None
                same_mod = [s for s in cands if self.files_by_id[s.file_id].module_id == mod]
                if same_mod:
                    chosen, strat = same_mod, "same-module"
                elif len(cands) == 1:
                    chosen, strat = cands, "unique-name"
                else:
                    unresolved += 1
                    continue
            # `this.x()` / `self.x()` / `s.x()` with a receiver only makes sense for methods
            if c.receiver and c.receiver not in ("this", "self", "cls"):
                methods = [s for s in chosen if s.kind == "method"] or chosen
                chosen = methods
            if len(chosen) > 1:
                # homonyms found by name: the argument count trims the guesses, it does not make one of them proven
                strat += "-ambiguous"
                chosen = _fitting(chosen, c.arg_count)[:3]
            for s in chosen:
                edges.append(CallEdge(c.caller_id, s.id, c.line, strat))
        return edges, unresolved

    def _on_type(self, c, cands: list[SymbolInfo], qtype: str, lang) -> list[tuple[list[SymbolInfo], str]]:
        """The methods of the receiver's type and of the implementation it reaches; when none takes the arguments, the
        repo's methods the language calls on the receiver (C# extension methods)."""
        typed = self._methods_on(cands, c.callee_name, qtype, lang, c.arg_count)
        impl = lang.implementation_target(self.ctx, qtype, c.callee_name, self._owner(c.caller_id))
        impl_typed = self._methods_on(cands, c.callee_name, impl, lang, c.arg_count) if impl else []
        found = [(typed, "receiver-type"), (impl_typed, "receiver-type-impl")]
        if any(_fits(s, c.arg_count) for s in typed + impl_typed):
            return found
        return lang.extension_methods(self.ctx, [s for s in cands if _fits(s, c.arg_count)], qtype,
                                      c.receiver_type) or found

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
        impl = None if impl_found else lang.implementation_target(self.ctx, qtype, c.callee_name, self._owner(c.caller_id))
        for target, strategy in ((qtype, "inherited"), (impl, "inherited-impl")):
            t = self.type_by_q.get(target) if target else None
            if t is None or self._inside(c.caller_id, t.id) or (not caller_test and self.test_file.get(t.file_id, False)):
                continue                 # its own type (`this.ResponseAsync()` in a controller) says nothing new
            out.append(CallEdge(c.caller_id, t.id, c.line, strategy, c.callee_name))
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
                    out.setdefault(target.id, CallEdge(c.caller_id, target.id, c.line, "dispatch"))
        return list(out.values())

    def _methods_on(self, cands: list[SymbolInfo], name: str, qtype: str, lang, argc: int | None = None) -> list[SymbolInfo]:
        """The method declared on `qtype` or, failing that, on its nearest in-repo supertype — the overloads that
        accept `argc` arguments (all of them when none does: the arity read may be incomplete)."""
        for t in [qtype] + lang.supertypes(self.ctx, qtype):
            hit = [s for s in cands if s.qualified_name == f"{t}.{name}"]
            if hit:
                return _fitting(hit, argc)
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
        return Resolved(calls, imports, self.packages, uc, ui, self.ctx.namespaces)
