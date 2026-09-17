"""TypeScript / TSX / JavaScript support: one module, three grammars.

TS and TSX share `queries.scm`; plain JS uses `queries.javascript.scm` (no type-only nodes).
Imports: relative paths and `@/`, `~/`, `src/`, `#` aliases resolve to files (trying the usual
extensions and `index.*`); everything else is an npm package (`node:` = stdlib).
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path, PurePosixPath

from tree_sitter import Node

from ...core.model import FileInfo
from ..base import LanguageSupport, PackageFactory, ResolveContext
from .http import TsScanner

HERE = Path(__file__).parent

TS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".d.ts")
_IMPORT = re.compile(r"import\s+(?:type\s+)?(?:(\w+)\s*,?\s*)?(?:\*\s+as\s+(\w+))?\s*(?:\{([^}]*)\})?")
_BUILTINS = frozenset({"console", "Math", "JSON", "Object", "Array", "Promise", "Number", "String", "Date",
                       "process", "window", "document"})
_DECORATOR_ENTRY = re.compile(r"@(Get|Post|Put|Delete|Patch|All|MessagePattern|EventPattern|Cron|Query|Mutation|GrpcMethod"
                              r"|SqsMessageHandler|RabbitSubscribe|Process)\b")


def _try_paths(ctx: ResolveContext, base: PurePosixPath) -> FileInfo | None:
    for cand in [str(base)] + [f"{base}{e}" for e in TS_EXTS] + [f"{base}/index{e}" for e in TS_EXTS]:
        f = ctx.file_at(cand)
        if f:
            return f
    return None


class TypeScriptSupport(LanguageSupport):
    def import_bindings(self, stmt_text: str, stmt: Node, spec: str, src: bytes) -> list[str]:
        names: list[str] = []
        m = _IMPORT.search(stmt_text)
        if m:
            if m.group(1): names.append(m.group(1))
            if m.group(2): names.append(m.group(2))
            if m.group(3):
                for part in m.group(3).split(","):
                    part = part.strip()
                    if part:
                        names.append(part.split(" as ")[-1].strip())
        rq = re.search(r"(?:const|let|var)\s+(\w+)\s*=\s*require", stmt_text)
        if rq:
            names.append(rq.group(1))
        return names

    def resolve_import(self, ctx: ResolveContext, file: FileInfo, spec: str, pkg: PackageFactory) -> tuple[str, str] | None:
        here = PurePosixPath(file.path).parent
        if spec.startswith("."):
            t = _try_paths(ctx, PurePosixPath(posixpath.normpath(str(here / spec))))
            return (t.id, "File") if t else None
        if spec.startswith(("@/", "~/", "src/", "#")):
            tail = re.sub(r"^(@/|~/|#)", "", spec)          # path alias — try a few conventional roots
            for root in ("src", "", "app", "lib"):
                t = _try_paths(ctx, PurePosixPath(root) / tail if root else PurePosixPath(tail))
                if t:
                    return (t.id, "File")
            return None
        if spec.startswith("node:"):
            return (pkg("npm", spec, True), "Package")
        name = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
        return (pkg("npm", name, False), "Package")


def _make(lang_id: str, grammar: str, exts: tuple[str, ...], query: str) -> TypeScriptSupport:
    return TypeScriptSupport(
        id=lang_id, grammar=grammar, extensions=exts, query_file=HERE / query, stack="ts",
        manifests={"package.json": "npm-package"}, builtin_receivers=_BUILTINS, ecosystem="npm",
        http_scanner=TsScanner, decorator_entry=_DECORATOR_ENTRY,
    )


LANGUAGES = [
    _make("typescript", "typescript", (".ts", ".mts", ".cts"), "queries.scm"),
    _make("tsx", "tsx", (".tsx",), "queries.scm"),
    _make("javascript", "javascript", (".js", ".mjs", ".cjs", ".jsx"), "queries.javascript.scm"),
]
