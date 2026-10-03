"""Name-based resolution inside one repo (v0 — SCIP may enrich this in F1.2, see ADR-002).

Calls: candidate symbols with the callee's name, narrowed same-file → same-module → repo-unique.
Imports: each file's `LanguageSupport.resolve_import` maps a spec to a File or Module node, or to
an external `Package` node. Language-specific knowledge (extensions to try, stdlib detection,
namespaces, go.mod) lives in `languages/<lang>/symbols.py`.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .. import languages
from ..languages.base import ResolveContext
from . import ids
from .config import is_test_path
from .extract import CALLABLE_KINDS, FileExtractor
from .model import ExtractionResult, FileInfo, SymbolInfo

# receivers that are runtime builtins in some language — a call on them never targets repo code
BUILTIN_RECEIVERS: frozenset[str] = frozenset().union(*(l.builtin_receivers for l in languages.all()))


@dataclass
class CallEdge:
    caller_id: str
    callee_id: str
    line: int
    strategy: str          # receiver-type | receiver-type-impl | same-file | same-module | unique-name (+ "-ambiguous")


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


class Resolver:
    def __init__(self, result: ExtractionResult, extractors: list[FileExtractor]):
        self.r = result
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
        namespaces: dict[str, list[str]] = defaultdict(list)
        for fx in extractors:
            for ns in fx.namespaces:
                namespaces[ns].append(fx.file.id)
        self.packages: dict[str, PackageNode] = {}
        self.external_bindings: dict[str, set[str]] = defaultdict(set)   # file id -> names bound to external packages
        self.ctx = ResolveContext(self.root, self.files_by_path, self.modules_by_path, self.module_by_id,
                                  self.files_by_id, dict(namespaces), facts={fx.file.id: fx.facts for fx in extractors})
        self.test_file = {f.id: is_test_path(f.path) for f in result.files}
        for lang in languages.all():
            lang.resolve_setup(self.ctx)

    # -- calls -----------------------------------------------------------------------
    def resolve_calls(self) -> tuple[list[CallEdge], int]:
        edges: list[CallEdge] = []
        unresolved = 0
        for c in self.r.calls:
            cands = self.by_name.get(c.callee_name)
            if not cands:
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
                if not prod:
                    unresolved += 1
                    continue
                cands = prod
            # static receiver type (Go: struct field / parameter / constructor) picks the method among homonyms
            if c.receiver_type and caller_file is not None:
                lang = languages.by_id(caller_file.language)
                qtype = lang.resolve_receiver(self.ctx, caller_file, c.receiver_type, c.receiver_path) if lang else None
                if qtype:
                    typed = self._method_on(cands, c.callee_name, qtype, lang)
                    impl = lang.implementation_target(self.ctx, qtype, c.callee_name)
                    impl_typed = self._method_on(cands, c.callee_name, impl, lang) if impl else None
                    if typed is not None:
                        edges.append(CallEdge(c.caller_id, typed.id, c.line, "receiver-type"))
                    if impl_typed is not None:
                        edges.append(CallEdge(c.caller_id, impl_typed.id, c.line, "receiver-type-impl"))
                    if typed is None and impl_typed is None:
                        unresolved += 1      # the receiver's type is known and it has no such method here (inherited from a package): don't guess
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
                strat += "-ambiguous"
                chosen = chosen[:3]
            for s in chosen:
                edges.append(CallEdge(c.caller_id, s.id, c.line, strat))
        return edges, unresolved

    def _method_on(self, cands: list[SymbolInfo], name: str, qtype: str, lang) -> SymbolInfo | None:
        """The candidate declared on `qtype` or, failing that, on its nearest in-repo supertype."""
        for t in [qtype] + lang.supertypes(self.ctx, qtype):
            hit = [s for s in cands if s.qualified_name == f"{t}.{name}"]
            if len(hit) == 1:
                return hit[0]
        return None

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
        return Resolved(calls, imports, self.packages, uc, ui)
