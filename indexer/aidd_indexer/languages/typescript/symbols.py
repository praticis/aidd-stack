"""TypeScript / TSX / JavaScript support: one module, three grammars.

TS and TSX share `queries.scm`; plain JS uses `queries.javascript.scm` (no type-only nodes).
Imports: relative paths and `@/`, `~/`, `src/`, `#` aliases resolve to files (trying the usual
extensions and `index.*`); everything else is an npm package (`node:` = stdlib).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tree_sitter import Node

from ...core.model import FileInfo
from ...core.types import RepoTypes, TypeRef
from ..base import LanguageSupport, PackageFactory, ResolveContext
from .http import TsScanner
from .modules import Package, module_target
from .package_facts import package_facts_reader
from .type_facts import TsTypes, type_facts
from .type_index import Outside, TsTypeIndex, qualified, ref, typed

HERE = Path(__file__).parent
_IMPORT = re.compile(r"import\s+(?:type\s+)?(?:(\w+)\s*,?\s*)?(?:\*\s+as\s+(\w+))?\s*(?:\{([^}]*)\})?")
_BUILTINS = frozenset({"console", "Math", "JSON", "Object", "Array", "Promise", "Number", "String", "Date",
                       "process", "window", "document"})
_DECORATOR_ENTRY = re.compile(r"@(Get|Post|Put|Delete|Patch|All|MessagePattern|EventPattern|Cron|Query|Mutation|GrpcMethod"
                              r"|SqsMessageHandler|RabbitSubscribe|Process)\b")


class TypeScriptSupport(LanguageSupport):

    def package_facts(self, src: bytes):
        return package_facts_reader(src)

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

    def manifest_deps(self, rel_path: str, text: str) -> tuple[list[str], list[tuple[str, str]]]:
        """package.json: `name` publishes; `dependencies` + `peerDependencies` require (dev deps are
        tooling, not a runtime link between services). Workspace/file specs still count — they
        name the package."""
        try:
            data = json.loads(text)
        except ValueError:
            return [], []
        if not isinstance(data, dict):
            return [], []
        names = [data["name"]] if isinstance(data.get("name"), str) else []
        deps = []
        for section in ("dependencies", "peerDependencies"):
            block = data.get(section)
            if isinstance(block, dict):
                deps.extend((k, str(v)) for k, v in block.items())
        return names, deps

    def resolve_import(self, ctx: ResolveContext, file: FileInfo, spec: str, pkg: PackageFactory) -> tuple[str, str] | None:
        found = module_target(ctx, file, spec)
        if isinstance(found, Package):
            return (pkg("npm", found.name, found.platform), "Package")
        return (found.id, "File") if found is not None else None

    # ---- types: one index for TS's three languages, whose files import one another
    def file_facts(self, root: Node, src: bytes, index: Any = None) -> TsTypes:
        return type_facts(root)

    def type_index(self, ctx: ResolveContext) -> TsTypeIndex:
        return TsTypeIndex(ctx)

    def _types(self, ctx: ResolveContext) -> TsTypeIndex:
        """The repo's TS type index: the one the HTTP pass shares, or one over this context."""
        if ctx.types is None:
            ctx.types = RepoTypes(ctx)
        return ctx.types.of(self.id)

    def resolve_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str,
                         path: tuple[str, ...]) -> str | None:
        found = typed(self._types(ctx), file.path, receiver_type, path)
        return qualified(found) if isinstance(found, TypeRef) and found.name else None

    def external_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str,
                          path: tuple[str, ...]) -> tuple[str, bool] | None:
        """A receiver whose chain ends in a package's type: no method of the repo is its."""
        found = typed(self._types(ctx), file.path, receiver_type, path)
        return (found.name, True) if isinstance(found, Outside) else None

    def supertypes(self, ctx: ResolveContext, qualified_type: str) -> list[str]:
        return [qualified(t) for t in self._types(ctx).supertypes(ref(qualified_type))]

    def has_external_base(self, ctx: ResolveContext, qualified_type: str) -> bool:
        return self._types(ctx).outside_base(ref(qualified_type))


def _make(lang_id: str, grammar: str, exts: tuple[str, ...], query: str) -> TypeScriptSupport:
    return TypeScriptSupport(
        id=lang_id, grammar=grammar, extensions=exts, query_file=HERE / query, stack="ts", type_family="typescript",
        manifests={"package.json": "npm-package"}, builtin_receivers=_BUILTINS, ecosystem="npm",
        http_scanner=TsScanner, decorator_entry=_DECORATOR_ENTRY,
    )


LANGUAGES = [
    _make("typescript", "typescript", (".ts", ".mts", ".cts"), "queries.scm"),
    _make("tsx", "tsx", (".tsx",), "queries.scm"),
    _make("javascript", "javascript", (".js", ".mjs", ".cjs", ".jsx"), "queries.javascript.scm"),
]
