"""Python support: `_name` = private, docstrings as docs, `def` inside a class = method,
relative/absolute imports resolved to files (module root, repo root, `src/`), else a PyPI package
(stdlib detected via `sys.stdlib_module_names`).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path, PurePosixPath

from tree_sitter import Node

from ...core.model import FileInfo, SymbolInfo
from ..base import LanguageSupport, PackageFactory, ResolveContext, node_text
from .http import PyScanner

HERE = Path(__file__).parent

STDLIB = set(getattr(sys, "stdlib_module_names", ()))
_IMPORT = re.compile(r"^\s*(?:from\s+[\w.]+\s+)?import\s+(.*)$", re.S)
_DECORATOR_ENTRY = re.compile(r"@(app|router|api|bp|blueprint)\.(get|post|put|delete|patch|route|websocket)\b")


class PythonSupport(LanguageSupport):
    def adjust_kind(self, kind: str, parent: SymbolInfo | None) -> str:
        if kind == "function" and parent is not None and parent.kind == "class":
            return "method"
        return kind

    def visibility(self, name: str, node: Node, src: bytes, first_line: str) -> str:
        return "private" if name.startswith("_") else "public"

    def doc_extra(self, node: Node, src: bytes) -> list[str]:
        body = node.child_by_field_name("body")
        if body is not None and body.child_count and body.children[0].type == "expression_statement":
            first = body.children[0].children[0] if body.children[0].child_count else None
            if first is not None and first.type == "string":
                return [node_text(first, src)]
        return []

    def import_bindings(self, stmt_text: str, stmt: Node, spec: str, src: bytes) -> list[str]:
        m = _IMPORT.match(stmt_text)
        if not m:
            return []
        names = []
        for part in m.group(1).replace("(", "").replace(")", "").split(","):
            part = part.strip()
            if not part:
                continue
            if " as " in part:
                names.append(part.split(" as ")[-1].strip())
            else:
                names.append(part.split(".")[0])
        return names

    def resolve_import(self, ctx: ResolveContext, file: FileInfo, spec: str, pkg: PackageFactory) -> tuple[str, str] | None:
        here = PurePosixPath(file.path).parent
        if spec.startswith("."):
            dots = len(spec) - len(spec.lstrip("."))
            base = here
            for _ in range(dots - 1):
                base = base.parent
            tail = spec[dots:].replace(".", "/")
            base = base / tail if tail else base
            for cand in (f"{base}.py", f"{base}/__init__.py"):
                t = ctx.file_at(cand.lstrip("./"))
                if t:
                    return (t.id, "File")
            return None
        parts = spec.split(".")
        mod = ctx.module_by_id.get(file.module_id)
        for root in {mod.path if mod else "", "", "src"}:
            base = PurePosixPath(root) / "/".join(parts) if root else PurePosixPath("/".join(parts))
            for cand in (f"{base}.py", f"{base}/__init__.py"):
                t = ctx.file_at(str(cand))
                if t:
                    return (t.id, "File")
        top = parts[0]
        return (pkg("pypi", top, top in STDLIB), "Package")


LANGUAGES = [
    PythonSupport(
        id="python", grammar="python", extensions=(".py",), query_file=HERE / "queries.scm", stack="python",
        manifests={"pyproject.toml": "py-package", "setup.py": "py-package", "requirements.txt": "py-package"},
        ecosystem="pypi", http_scanner=PyScanner, decorator_entry=_DECORATOR_ENTRY,
    ),
]
