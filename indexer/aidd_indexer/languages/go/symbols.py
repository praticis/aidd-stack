"""Go language support: packages as modules, receiver-scoped methods, go.mod based import resolution."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from tree_sitter import Node

from ...core import ids
from ...core.model import FileInfo, ModuleInfo, RepoInfo, SymbolInfo
from ..base import LanguageSupport, PackageFactory, ResolveContext, node_text, walk
from .http import GoScanner

HERE = Path(__file__).parent


def _go_module_path(root: Path, module: ModuleInfo) -> str | None:
    gm = root / module.path / "go.mod" if module.path else root / "go.mod"
    if not gm.exists():
        return None
    for line in gm.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("module "):
            return line.split(None, 1)[1].strip()
    return None


def _receiver(node: Node, src: bytes) -> str | None:
    recv = node.child_by_field_name("receiver")
    if recv is None:
        return None
    for tid in walk(recv):
        if tid.type == "type_identifier":
            return node_text(tid, src)
    return None


class GoSupport(LanguageSupport):
    # ---- discovery: every directory with .go files is a package — the unit imports point at
    def discover_modules(self, repo: RepoInfo, rel_files: list[str], modules: dict[str, ModuleInfo]) -> None:
        for r in rel_files:
            p = PurePosixPath(r)
            if p.suffix == ".go" and not p.name.endswith("_test.go"):
                d = str(p.parent) if str(p.parent) != "." else ""
                if d not in modules:
                    modules[d] = ModuleInfo(
                        id=ids.module(repo.tenant, repo.name, repo.ref, d),
                        name=(p.parent.name if d else repo.name),
                        path=d,
                        kind="go-package",
                    )

    # ---- symbols
    def module_prefix(self, file: FileInfo) -> str:
        d = str(PurePosixPath(file.path).parent)
        return "" if d == "." else d.replace("/", ".")

    def qualified_name(self, prefix: str, chain: list[str], name: str) -> str:
        return ".".join(([prefix] if prefix else []) + chain + [name])

    def scope_chain(self, dnode: Node, src: bytes, chain: list[str], kind: str, file_namespace: str | None) -> list[str]:
        if kind == "method":
            recv = _receiver(dnode, src)
            if recv:
                return [recv]
        return chain

    def visibility(self, name: str, node: Node, src: bytes, first_line: str) -> str:
        return "public" if name[:1].isupper() else "private"

    def import_bindings(self, stmt_text: str, stmt: Node, spec: str, src: bytes) -> list[str]:
        alias = stmt.child_by_field_name("name")
        if alias is not None:
            return [node_text(alias, src)]
        base = spec.rstrip("/").split("/")[-1]
        base = re.sub(r"^v\d+$", "", base) or spec.rstrip("/").split("/")[-2]
        return [re.sub(r"[-.].*$", "", base) or base]

    # ---- resolution
    def resolve_setup(self, ctx: ResolveContext) -> None:
        # module paths from go.mod, longest first
        ctx.extra["go_modules"] = sorted(
            ((mp, m) for m in ctx.modules_by_path.values()
             if m.kind == "go-module" and (mp := _go_module_path(ctx.root, m))),
            key=lambda t: -len(t[0]),
        )

    def resolve_import(self, ctx: ResolveContext, file: FileInfo, spec: str, pkg: PackageFactory) -> tuple[str, str] | None:
        for mp, m in ctx.extra.get("go_modules", ()):
            if spec == mp or spec.startswith(mp + "/"):
                rel = spec[len(mp):].strip("/")
                pkg_dir = "/".join(p for p in (m.path, rel) if p)
                mod = ctx.modules_by_path.get(pkg_dir)
                return (mod.id, "Module") if mod else None
        first = spec.split("/")[0]
        stdlib = "." not in first
        name = spec if stdlib else "/".join(spec.split("/")[:3])
        return (pkg("go", name, stdlib), "Package")

    def link_symbols(self, symbols: list[SymbolInfo], files_by_id: dict[str, FileInfo]) -> None:
        """Methods → receiver struct as parent (`pkg.Type.Method` → `pkg.Type`)."""
        by_q = {s.qualified_name: s for s in symbols if s.kind in ("struct", "type", "interface")}
        for s in symbols:
            if s.kind == "method" and s.parent_id is None and files_by_id[s.file_id].language == self.id:
                owner = s.qualified_name.rsplit(".", 1)[0]
                if owner in by_q:
                    s.parent_id = by_q[owner].id


LANGUAGES = [
    GoSupport(
        id="go", grammar="go", extensions=(".go",), query_file=HERE / "queries.scm", stack="go",
        manifests={"go.mod": "go-module"}, ecosystem="go", http_scanner=GoScanner,
        entry_point_hints=("http.ResponseWriter", "*gin.Context", "echo.Context", "*fiber.Ctx", "context.Context, req"),
    ),
]
