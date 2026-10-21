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
from ...core.types import Field, RepoTypes, TypeRef, Unknown
from ...tree import NodeCache
from ..base import LanguageSupport, PackageFactory, ResolveContext, node_text, walk
from .package_facts import read_package_facts
from .type_facts import TYPE_NODES, GoTypes, import_aliases, receiver_type, type_facts, type_text
from .type_index import DEPTH, GoTypeIndex, module_paths
from .http import GoScanner

HERE = Path(__file__).parent


_FUNC_NODES = ("function_declaration", "method_declaration", "func_literal")
def _declared_type(name: str, scope: Node, src: bytes, before: int) -> str | None:
    """Type of local variable `name` inside `scope` (a function): receiver, parameter, `var x T`,
    `x := T{}` / `&T{}`, or `x := pkg.New(...)` (reported as `call:pkg.New` for the resolver)."""
    for pl in [c for c in scope.children if c.type == "parameter_list"]:      # receiver + params
        for pd in pl.children:
            if pd.type != "parameter_declaration":
                continue
            names = [c for c in pd.children if c.type == "identifier"]
            typ = next((c for c in pd.children if c.type in TYPE_NODES or c.type.endswith("_type")), None)
            if any(node_text(nm, src) == name for nm in names):
                return type_text(typ, src)
    best: str | None = None
    for start, value in _DECLARATIONS.get(scope, src).get(name, ()):
        if start >= before:
            break
        best = value
    return best


def _declarations(scope: Node, src: bytes) -> dict[str, list[tuple[int, str | None]]]:
    """name → (where, the type it gets there) for each `x := ..` and `var x T` under `scope`, function literals
    included, in document order. A declaration whose value is not a type the code shows gives None: it hides an
    earlier one."""
    out: dict[str, list[tuple[int, str | None]]] = {}
    for d in walk(scope):
        if d.type == "short_var_declaration":
            for name, value in _short_var_types(d, src):
                out.setdefault(name, []).append((d.start_byte, value))
        elif d.type == "var_spec" and d.child_by_field_name("type") is not None:
            typ = type_text(d.child_by_field_name("type"), src)
            for nm in (c for c in d.children if c.type == "identifier"):
                out.setdefault(node_text(nm, src), []).append((d.start_byte, typ))
    return out


def _short_var_types(d: Node, src: bytes) -> list[tuple[str, str | None]]:
    """(name, type) for each name `x := ..` declares and types: `T{}` / `&T{}`, `call:pkg.New` (with `#i` for one
    result of a multi-value call), or None for any other value. A call through anything but a name gives nothing."""
    left, right = d.child_by_field_name("left"), d.child_by_field_name("right")
    if left is None or right is None:
        return []
    lefts = [c for c in left.children if c.is_named]
    rights = [c for c in right.children if c.is_named]
    out = []
    for i, lft in enumerate(lefts):
        r = rights[i] if i < len(rights) else rights[0] if len(rights) == 1 and rights[0].type == "call_expression" else None
        if r is not None and r.type == "unary_expression":                     # &T{...}
            r = next((c for c in r.children if c.is_named), r)
        if r is None:
            continue
        if r.type == "composite_literal":
            out.append((node_text(lft, src), type_text(r.child_by_field_name("type"), src)))
        elif r.type != "call_expression":
            out.append((node_text(lft, src), None))
        elif (fn := r.child_by_field_name("function")) is not None and fn.type in ("identifier", "selector_expression"):
            many = f"#{i}" if len(lefts) > 1 and len(rights) == 1 else ""      # `uc, repo := setup(t)`
            out.append((node_text(lft, src), "call:" + node_text(fn, src) + many))
    return out


_DECLARATIONS = NodeCache(_declarations)


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
        # receiver = `uc.policy` (selector chain) or `p` (identifier); anything else (call results,
        # index expressions) is not followed.
        chain: list[str] = []
        n = receiver
        while n.type == "selector_expression":
            fld = n.child_by_field_name("field")
            if fld is None:
                return None
            chain.insert(0, node_text(fld, src))
            n = n.child_by_field_name("operand")
            if n is None:
                return None
        if n.type != "identifier":
            return None
        base = node_text(n, src)
        scope = call.parent
        while scope is not None and scope.type not in _FUNC_NODES:
            scope = scope.parent
        if scope is None:
            return None
        typ = _declared_type(base, scope, src, call.start_byte)
        if typ is None and scope.type == "func_literal":                      # closure: look at the enclosing function
            outer = scope.parent
            while outer is not None and outer.type not in _FUNC_NODES:
                outer = outer.parent
            if outer is not None:
                typ = _declared_type(base, outer, src, call.start_byte)
        return (typ, tuple(chain)) if typ else None

    def type_index(self, ctx: ResolveContext) -> GoTypeIndex:
        return GoTypeIndex(ctx)

    def _types(self, ctx: ResolveContext) -> GoTypeIndex:
        """The repo's Go type index: the one the HTTP pass shares, or one over this context."""
        if ctx.types is None:
            ctx.types = RepoTypes(ctx)
        return ctx.types.of(self.id)

    def resolve_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str, path: tuple[str, ...]) -> str | None:
        types = self._types(ctx)
        if receiver_type.startswith("call:"):                   # `x := pkg.New()`, `#i` for one of several results
            fn, _, idx = receiver_type[5:].partition("#")
            # a `#` of the call's own text (`doc.Find("#id").Children()`) numbers no result: no function has that name
            cur = types.return_type(fn, file.path, int(idx or 0)) if idx.isdecimal() or not idx else None
        else:
            cur = types.type_named(receiver_type, file.path)
        for name in path:
            if not isinstance(cur, TypeRef):
                return None
            found = types.field(cur, name)
            cur = found.type if isinstance(found, Field) else found
        return _qualified(cur) if isinstance(cur, TypeRef) else None

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
