"""Python support: `_name` = private, docstrings as docs, `def` inside a class = method,
relative/absolute imports resolved to files (module root, repo root, `src/`), else a PyPI package
(stdlib detected via `sys.stdlib_module_names`).
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path
from typing import Any

from tree_sitter import Node

from ...core.model import FileInfo, SymbolInfo
from ...core.types import RepoTypes, TypeRef, Unknown
from ..base import LanguageSupport, PackageFactory, ResolveContext, node_text
from .http import PyScanner
from .modules import module_file
from .package_facts import read_package_facts
from .receivers import receiver_of
from .scopes import PyScopes
from .type_facts import PyTypes, type_facts
from .type_index import Outside, PythonTypeIndex, qualified, ref, typed

HERE = Path(__file__).parent

STDLIB = set(getattr(sys, "stdlib_module_names", ()))
_IMPORT = re.compile(r"^\s*(?:from\s+[\w.]+\s+)?import\s+(.*)$", re.S)
_DECORATOR_ENTRY = re.compile(r"@(app|router|api|bp|blueprint)\.(get|post|put|delete|patch|route|websocket)\b")


_PY_REQ = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*([^;#]*)")


def _py_requirement(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith(("#", "-", "git+", "http://", "https://")):
        return None
    m = _PY_REQ.match(line)
    return (m.group(1), m.group(2).strip()) if m else None


class PythonSupport(LanguageSupport):

    def package_facts(self, src: bytes):
        return read_package_facts

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

    def manifest_deps(self, rel_path: str, text: str) -> tuple[list[str], list[tuple[str, str]]]:
        """pyproject.toml: `[project] name` publishes, `[project] dependencies` require (PEP 621;
        poetry's `[tool.poetry]` too). requirements.txt: one requirement per line."""
        if rel_path.endswith("requirements.txt"):
            return [], [d for d in (_py_requirement(l) for l in text.splitlines()) if d]
        if not rel_path.endswith("pyproject.toml"):
            return [], []
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return [], []
        project = data.get("project") or {}
        poetry = (data.get("tool") or {}).get("poetry") or {}
        names = [n for n in (project.get("name"), poetry.get("name")) if isinstance(n, str)]
        deps = [d for d in (_py_requirement(r) for r in project.get("dependencies") or [] if isinstance(r, str)) if d]
        for k, v in (poetry.get("dependencies") or {}).items():
            if k.lower() != "python":
                deps.append((k, v if isinstance(v, str) else str((v or {}).get("version", ""))))
        return names, deps

    def resolve_import(self, ctx: ResolveContext, file: FileInfo, spec: str, pkg: PackageFactory) -> tuple[str, str] | None:
        found = module_file(ctx, file, spec)
        if found is not None:
            return (found.id, "File")
        if spec.startswith("."):
            return None
        top = spec.split(".")[0]
        return (pkg("pypi", top, top in STDLIB), "Package")

    # ---- types: a module and a class are both namespaces
    def file_index(self, root: Node, src: bytes) -> PyScopes:
        return PyScopes(root, src)

    def file_facts(self, root: Node, src: bytes, index: Any = None) -> PyTypes:
        return type_facts(index if index is not None else PyScopes(root, src))

    def call_receiver(self, call: Node, receiver: Node, src: bytes,
                      index: Any = None) -> tuple[str, tuple[str, ...]] | Unknown:
        if index is None:
            root = call
            while root.parent is not None:
                root = root.parent
            index = PyScopes(root, src)
        return receiver_of(receiver, index)

    def type_index(self, ctx: ResolveContext) -> PythonTypeIndex:
        return PythonTypeIndex(ctx)

    def _types(self, ctx: ResolveContext) -> PythonTypeIndex:
        """The repo's Python type index: the one the HTTP pass shares, or one over this context."""
        if ctx.types is None:
            ctx.types = RepoTypes(ctx)
        return ctx.types.of(self.id)

    def resolve_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str, path: tuple[str, ...]) -> str | None:
        """The receiver's type; none for a class with a base the index cannot see, which may give the method."""
        types = self._types(ctx)
        found = typed(types, file.path, receiver_type, path)
        return qualified(found) if isinstance(found, TypeRef) and not isinstance(types.mro(found), Unknown) else None

    def external_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str,
                          path: tuple[str, ...]) -> tuple[str, bool] | None:
        """A receiver whose chain ends in a package's class, module or function: no method of the repo is its."""
        found = typed(self._types(ctx), file.path, receiver_type, path)
        return (found.name, True) if isinstance(found, Outside) else None

    def supertypes(self, ctx: ResolveContext, qualified_type: str) -> list[str]:
        return [qualified(t) for t in self._types(ctx).supertypes(ref(qualified_type))]

    def has_external_base(self, ctx: ResolveContext, qualified_type: str) -> bool:
        return self._types(ctx).outside_base(ref(qualified_type))

    def member_name(self, owner: str, name: str) -> str:
        return f"{owner}.{name}" if ":" in owner else f"{owner}:{name}"


LANGUAGES = [
    PythonSupport(
        id="python", grammar="python", extensions=(".py",), query_file=HERE / "queries.scm", stack="python",
        manifests={"pyproject.toml": "py-package", "setup.py": "py-package", "requirements.txt": "py-package"},
        ecosystem="pypi", http_scanner=PyScanner, decorator_entry=_DECORATOR_ENTRY,
    ),
]
