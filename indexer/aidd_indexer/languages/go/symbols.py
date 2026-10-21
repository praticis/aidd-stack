"""Go language support: packages as modules, receiver-scoped methods, go.mod based import resolution,
and static receiver types for method calls (`uc.policy.Validate()` → `password.Policy.Validate`). A call
on an interface of the repo also reaches the one production type whose method set covers it
(`uc.repo.Save()` → `store.MemRepo.Save`, strategy `receiver-type-impl`)."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from tree_sitter import Node

from ...core import ids
from ...core.model import FileInfo, ModuleInfo, RepoInfo, SymbolInfo
from ...core.types import RepoTypes, TypeRef, Unknown
from ..base import LanguageSupport, PackageFactory, ResolveContext, node_text
from .package_facts import read_package_facts
from .type_facts import GoTypes, import_aliases, receiver_type, type_facts
from .locals import declared_type, receiver_chain
from .type_index import DEPTH, GoTypeIndex, module_paths, typed
from .http import GoScanner

HERE = Path(__file__).parent


def _ref(qualified_type: str) -> TypeRef:
    package, _, name = qualified_type.rpartition(".")
    return TypeRef(package, name)


def _qualified(t: TypeRef) -> str:
    return f"{t.package}.{t.name}" if t.package else t.name


_GO_MODULE_LINE = re.compile(r"^module\s+(\S+)", re.M)
_GO_REQUIRE_LINE = re.compile(r"^\s*(?:require\s+)?([a-zA-Z0-9.\-_~/]+\.[a-zA-Z0-9.\-_~/]+)\s+(v[^\s/]+)(?:\s*//.*)?$", re.M)


_SPECS = frozenset({"type_spec", "type_alias", "const_spec", "var_spec"})
_DECLS = frozenset({"type_declaration", "const_declaration", "var_declaration"})


class GoSupport(LanguageSupport):

    def package_facts(self, src: bytes):
        return read_package_facts

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
            recv = receiver_type(dnode, src)
            if recv:
                return [recv]
        return chain

    def def_node(self, node: Node) -> Node:
        # `type X struct{}` / `const X = 1`: the declaration holds the doc comment and the keyword;
        # inside a block (`const ( A ...; B ... )`) each spec is a definition of its own
        p = node.parent
        if node.type in _SPECS and p is not None and p.type in _DECLS \
                and sum(1 for c in p.named_children if c.type in _SPECS) == 1:
            return p
        return node

    def visibility(self, name: str, node: Node, src: bytes, first_line: str) -> str:
        return "public" if name[:1].isupper() else "private"

    def import_bindings(self, stmt_text: str, stmt: Node, spec: str, src: bytes) -> list[str]:
        return import_aliases(stmt, spec, src)

    # ---- static receiver types
    def file_facts(self, root: Node, src: bytes) -> GoTypes:
        return type_facts(root, src)

    def arity(self, node: Node, src: bytes) -> tuple[int, int | None] | None:
        pl = node.child_by_field_name("parameters")
        if pl is None:
            return None
        n, variadic = 0, False
        for pd in pl.children:
            if pd.type == "parameter_declaration":
                n += max(1, sum(1 for c in pd.children if c.type == "identifier"))   # `a, b int` = 2
            elif pd.type == "variadic_parameter_declaration":
                variadic = True
        return (n, None if variadic else n)

    def call_arg_count(self, call: Node, src: bytes) -> int | None:
        args = call.child_by_field_name("arguments")
        if args is None or any(a.type == "variadic_argument" for a in args.children):
            return None                                     # `f(xs...)`: unknown
        return sum(1 for a in args.children if a.is_named and a.type != "comment")

    def call_receiver(self, call: Node, receiver: Node, src: bytes) -> tuple[str, tuple[str, ...]] | None:
        found = receiver_chain(receiver, src)
        typ = declared_type(node_text(found[0], src), found[0], src) if found is not None else None
        return (typ, found[1]) if typ else None

    def type_index(self, ctx: ResolveContext) -> GoTypeIndex:
        return GoTypeIndex(ctx)

    def _types(self, ctx: ResolveContext) -> GoTypeIndex:
        """The repo's Go type index: the one the HTTP pass shares, or one over this context."""
        if ctx.types is None:
            ctx.types = RepoTypes(ctx)
        return ctx.types.of(self.id)

    def resolve_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str, path: tuple[str, ...]) -> str | None:
        found = typed(self._types(ctx), file.path, receiver_type, path)
        return _qualified(found) if found is not None else None

    # ---- resolution
    def manifest_deps(self, rel_path: str, text: str) -> tuple[list[str], list[tuple[str, str]]]:
        """go.mod: `module` publishes; `require` lines (single or block) are direct deps unless
        marked `// indirect`."""
        names = _GO_MODULE_LINE.findall(text)
        deps = [(m.group(1), m.group(2)) for m in _GO_REQUIRE_LINE.finditer(text) if "// indirect" not in m.group(0)]
        return names, deps

    def resolve_setup(self, ctx: ResolveContext) -> None:
        ctx.extra["go_modules"] = module_paths(ctx)

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

    def supertypes(self, ctx: ResolveContext, qualified_type: str) -> list[str]:
        """The repo's types the struct or interface embeds, the shallowest first: their methods are promoted."""
        return [_qualified(t) for t in self._types(ctx).embedded(_ref(qualified_type))]

    def has_external_base(self, ctx: ResolveContext, qualified_type: str) -> bool:
        """A struct embedding (or an interface embedding) a type of another module: its methods are promoted."""
        return self._external_base(self._types(ctx), _ref(qualified_type), 0)

    def _external_base(self, types: GoTypeIndex, of: TypeRef, depth: int) -> bool:
        bases = types.bases(of) if depth <= DEPTH else []
        return not isinstance(bases, Unknown) and any(
            isinstance(b, Unknown) or self._external_base(types, b, depth + 1) for b in bases)

    def implementation_target(self, ctx: ResolveContext, qualified_type: str, method: str,
                              from_type: str | None = None) -> str | None:
        types, interface = self._types(ctx), _ref(qualified_type)
        found = types.implementers(interface)
        if isinstance(found, Unknown) or len(found) != 1 or isinstance(types.method(interface, method), Unknown):
            return None
        return _qualified(found[0])

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
