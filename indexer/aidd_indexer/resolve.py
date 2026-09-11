"""Name-based resolution inside one repo (v0 — SCIP replaces this in F1.2).

Calls: candidate symbols with the callee's name, narrowed same-file →
same-module → repo-unique. Imports: relative/module paths resolved to File
or Module nodes; anything else becomes an external `Package` node.
"""

from __future__ import annotations

import posixpath
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from . import ids
from .extract import CALLABLE_KINDS, FileExtractor
from .model import ExtractionResult, FileInfo, ModuleInfo, SymbolInfo

TS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".d.ts")
PY_STDLIB = set(getattr(sys, "stdlib_module_names", ()))
CS_FRAMEWORK_ROOTS = {"System", "Microsoft"}
BUILTIN_RECEIVERS = {"console", "Math", "JSON", "Object", "Array", "Promise", "Number", "String", "Date",
                     "process", "window", "document", "Console", "Task", "String", "Enumerable", "Convert"}


@dataclass
class CallEdge:
    caller_id: str
    callee_id: str
    line: int
    strategy: str          # same-file | same-module | unique-name (+ "-ambiguous")


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


def _go_module_path(root: Path, module: ModuleInfo) -> str | None:
    gm = root / module.path / "go.mod" if module.path else root / "go.mod"
    if not gm.exists():
        return None
    for line in gm.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("module "):
            return line.split(None, 1)[1].strip()
    return None


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
        self.cs_namespaces: dict[str, list[str]] = defaultdict(list)
        for fx in extractors:
            for ns in fx.namespaces:
                self.cs_namespaces[ns].append(fx.file.id)
        self.packages: dict[str, PackageNode] = {}
        self.external_bindings: dict[str, set[str]] = defaultdict(set)   # file id -> names bound to external packages
        # Go module paths, longest first
        self.go_modules = sorted(
            ((mp, m) for m in result.modules if m.kind == "go-module" and (mp := _go_module_path(self.root, m))),
            key=lambda t: -len(t[0]),
        )

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

    # -- imports ---------------------------------------------------------------------
    def _pkg(self, ecosystem: str, name: str, stdlib: bool = False) -> PackageNode:
        pid = ids.package(self.r.repo.tenant, ecosystem, name)
        if pid not in self.packages:
            self.packages[pid] = PackageNode(pid, name, ecosystem, stdlib)
        return self.packages[pid]

    def _file_at(self, rel: str) -> FileInfo | None:
        return self.files_by_path.get(rel)

    def _try_ts_paths(self, base: PurePosixPath) -> FileInfo | None:
        for cand in [str(base)] + [f"{base}{e}" for e in TS_EXTS] + [f"{base}/index{e}" for e in TS_EXTS]:
            f = self._file_at(cand)
            if f:
                return f
        return None

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
        lang = f.language
        here = PurePosixPath(f.path).parent

        if lang in ("typescript", "tsx", "javascript"):
            if spec.startswith("."):
                base = PurePosixPath(posixpath.normpath(str(here / spec)))
                t = self._try_ts_paths(base)
                return (t.id, "File") if t else None
            if spec.startswith(("@/", "~/", "src/", "#")):
                # path alias — try a few conventional roots
                tail = re.sub(r"^(@/|~/|#)", "", spec)
                for root in ("src", "", "app", "lib"):
                    t = self._try_ts_paths(PurePosixPath(root) / tail if root else PurePosixPath(tail))
                    if t:
                        return (t.id, "File")
                return None
            if spec.startswith("node:"):
                return (self._pkg("npm", spec, stdlib=True).id, "Package")
            name = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
            return (self._pkg("npm", name).id, "Package")

        if lang == "go":
            for mp, m in self.go_modules:
                if spec == mp or spec.startswith(mp + "/"):
                    rel = spec[len(mp):].strip("/")
                    pkg_dir = "/".join(p for p in (m.path, rel) if p)
                    mod = self.modules_by_path.get(pkg_dir)
                    return (mod.id, "Module") if mod else None
            first = spec.split("/")[0]
            stdlib = "." not in first
            name = spec if stdlib else "/".join(spec.split("/")[:3])
            return (self._pkg("go", name, stdlib=stdlib).id, "Package")

        if lang == "python":
            if spec.startswith("."):
                dots = len(spec) - len(spec.lstrip("."))
                base = here
                for _ in range(dots - 1):
                    base = base.parent
                tail = spec[dots:].replace(".", "/")
                base = base / tail if tail else base
                for cand in (f"{base}.py", f"{base}/__init__.py"):
                    t = self._file_at(cand.lstrip("./"))
                    if t:
                        return (t.id, "File")
                return None
            parts = spec.split(".")
            mod = self.module_by_id.get(f.module_id)
            for root in {mod.path if mod else "", "", "src"}:
                base = PurePosixPath(root) / "/".join(parts) if root else PurePosixPath("/".join(parts))
                for cand in (f"{base}.py", f"{base}/__init__.py"):
                    t = self._file_at(str(cand))
                    if t:
                        return (t.id, "File")
            top = parts[0]
            return (self._pkg("pypi", top, stdlib=top in PY_STDLIB).id, "Package")

        if lang == "csharp":
            files = self.cs_namespaces.get(spec)
            if files:
                # one edge per declaring file would explode on big namespaces; point at the first
                # file's module instead, which is the meaningful unit for C#.
                fid = files[0]
                mod_id = self.files_by_id[fid].module_id
                return (mod_id, "Module")
            root = spec.split(".")[0]
            return (self._pkg("nuget", spec, stdlib=root in CS_FRAMEWORK_ROOTS).id, "Package")

        return None

    # -- Go receivers → parent struct ------------------------------------------------
    def link_go_receivers(self) -> None:
        by_q = {s.qualified_name: s for s in self.r.symbols if s.kind in ("struct", "type", "interface")}
        for s in self.r.symbols:
            if s.kind == "method" and s.parent_id is None and self.files_by_id[s.file_id].language == "go":
                owner = s.qualified_name.rsplit(".", 1)[0]
                if owner in by_q:
                    s.parent_id = by_q[owner].id

    def run(self) -> Resolved:
        self.link_go_receivers()
        imports, ui = self.resolve_imports()      # first: populates external_bindings
        calls, uc = self.resolve_calls()
        return Resolved(calls, imports, self.packages, uc, ui)
