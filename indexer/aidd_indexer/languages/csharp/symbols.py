"""C# support: namespaces (block and file-scoped) prefix qualified names; `using X;` resolves to the
module that declares namespace X, otherwise to a NuGet package (System.* / Microsoft.* = framework).
"""

from __future__ import annotations

import re
from pathlib import Path

from tree_sitter import Node

from ...core.model import FileInfo
from ..base import LanguageSupport, PackageFactory, ResolveContext, node_text, walk
from .http import CsScanner

HERE = Path(__file__).parent

NAMESPACE_NODES = frozenset({"namespace_declaration", "file_scoped_namespace_declaration"})
FRAMEWORK_ROOTS = {"System", "Microsoft"}
_BUILTINS = frozenset({"Console", "Task", "String", "Enumerable", "Convert"})
_DECORATOR_ENTRY = re.compile(r"\[(HttpGet|HttpPost|HttpPut|HttpDelete|HttpPatch|Route|Function|ServiceBusTrigger|QueueTrigger)\b")


class CSharpSupport(LanguageSupport):
    def module_prefix(self, file: FileInfo) -> str:
        return ""                                   # namespaces carry the scope

    def qualified_name(self, prefix: str, chain: list[str], name: str) -> str:
        return ".".join(chain + [name])

    def scope_chain(self, dnode: Node, src: bytes, chain: list[str], kind: str, file_namespace: str | None) -> list[str]:
        if file_namespace and not any(a.type in NAMESPACE_NODES for a in _ancestors(dnode)):
            return [file_namespace] + chain
        return chain

    def file_scope(self, root: Node, src: bytes) -> tuple[list[str], str | None]:
        namespaces: list[str] = []
        file_ns: str | None = None
        for n in walk(root):
            if n.type in NAMESPACE_NODES:
                nm = n.child_by_field_name("name")
                if nm is not None:
                    namespaces.append(node_text(nm, src))
                    if n.type == "file_scoped_namespace_declaration":
                        file_ns = node_text(nm, src)
        return namespaces, file_ns

    def resolve_import(self, ctx: ResolveContext, file: FileInfo, spec: str, pkg: PackageFactory) -> tuple[str, str] | None:
        files = ctx.namespaces.get(spec)
        if files:
            # one edge per declaring file would explode on big namespaces; point at the first
            # file's module instead, which is the meaningful unit for C#.
            return (ctx.files_by_id[files[0]].module_id, "Module")
        root = spec.split(".")[0]
        return (pkg("nuget", spec, root in FRAMEWORK_ROOTS), "Package")


def _ancestors(node: Node):
    n = node.parent
    while n is not None:
        yield n
        n = n.parent


LANGUAGES = [
    CSharpSupport(
        id="csharp", grammar="csharp", extensions=(".cs",), query_file=HERE / "queries.scm", stack="dotnet",
        manifest_suffixes={".csproj": "csproj", ".fsproj": "fsproj"}, builtin_receivers=_BUILTINS, ecosystem="nuget",
        http_scanner=CsScanner, namespace_nodes=NAMESPACE_NODES,
        entry_point_hints=("[HttpGet", "[HttpPost", "[HttpPut", "[HttpDelete", "[HttpPatch", "[Route", "IActionResult"),
        decorator_entry=_DECORATOR_ENTRY,
    ),
]
