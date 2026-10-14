"""C# support: namespaces (block and file-scoped) prefix qualified names; `using X;` resolves to the
module that declares namespace X, otherwise to a NuGet package (System.* / Microsoft.* = framework).
Static receiver types for method calls (`this._query.FindByIdAsync()` → `IAccountQuery.FindByIdAsync`)
and interface → unique implementer (`AccountReadRepository`), the usual DI shape. Mediator dispatch
(`mediator.Send(new X())` → the `Handle` of `IRequestHandler<X, ..>`) through the generic arguments
of base lists: MediatR built in, an organization's own bus declared by its convention (core/dispatch.py).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tree_sitter import Node

from ...core.dispatch import DispatchRule
from ...core.model import FileInfo
from ..base import LanguageSupport, PackageFactory, ResolveContext, node_text, walk
from .http import CsScanner

HERE = Path(__file__).parent

NAMESPACE_NODES = frozenset({"namespace_declaration", "file_scoped_namespace_declaration"})
FRAMEWORK_ROOTS = {"System", "Microsoft"}
_BUILTINS = frozenset({"Console", "Task", "String", "Enumerable", "Convert"})
# MediatR (`IMediator` / `ISender` / `IPublisher`): public, so on in every C# repo. Precise because the edge needs
# a handler of that exact message type in the repo. An organization's own bus goes in its convention.
_MEDIATR = (DispatchRule(frozenset({"Send"}), frozenset({"IRequestHandler"})),
            DispatchRule(frozenset({"Publish"}), frozenset({"INotificationHandler"})))
_DECORATOR_ENTRY = re.compile(r"\[(HttpGet|HttpPost|HttpPut|HttpDelete|HttpPatch|Route|Function|ServiceBusTrigger|QueueTrigger)\b")


_CS_PACKAGE_ID = re.compile(r"<PackageId>\s*([^<]+?)\s*</PackageId>")
_CS_ASSEMBLY_NAME = re.compile(r"<AssemblyName>\s*([^<]+?)\s*</AssemblyName>")
_CS_PACKAGE_REF = re.compile(r"<PackageReference\b([^>]*)/?>", re.S)
_CS_ATTR = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


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

    # ---- static receiver types
    def file_facts(self, root: Node, src: bytes) -> dict[str, Any]:
        types: dict[str, dict[str, Any]] = {}
        usings: list[str] = []
        for n in walk(root):
            if n.type == "using_directive":
                q = next((c for c in n.children if c.type in ("qualified_name", "identifier")), None)
                if q is not None:
                    usings.append(node_text(q, src))
            elif n.type in ("class_declaration", "record_declaration", "struct_declaration", "interface_declaration"):
                name = n.child_by_field_name("name")
                if name is None:
                    continue
                ns = None
                a = n.parent
                while a is not None:
                    if a.type in NAMESPACE_NODES:
                        nm = a.child_by_field_name("name")
                        ns = node_text(nm, src) if nm is not None else None
                        break
                    a = a.parent
                bl = next((c for c in n.children if c.type == "base_list"), None)
                bases = [t for t in (_type_text(c, src) for c in (bl.children if bl is not None else []) if c.is_named and c.type != "argument_list") if t]
                types[node_text(name, src)] = {"kind": n.type.split("_")[0], "ns": ns, "bases": bases,
                                               "generic_bases": _generic_bases(bl, src),
                                               "members": _members(n, src), "explicit": _explicit_impls(n, src)}
        _, file_ns = self.file_scope(root, src)
        for t in types.values():                       # file-scoped namespace: declarations are siblings, not children
            t["ns"] = t["ns"] or file_ns
        return {"types": types, "usings": usings, "file_ns": file_ns}

    def call_receiver(self, call: Node, receiver: Node, src: bytes) -> tuple[str, tuple[str, ...]] | None:
        chain: list[str] = []
        n = receiver
        while n.type == "member_access_expression":
            nm = n.child_by_field_name("name")
            if nm is None or nm.type != "identifier":
                return None
            chain.insert(0, node_text(nm, src))
            n = n.child_by_field_name("expression")
            if n is None:
                return None
        cls = _enclosing(call, ("class_declaration", "record_declaration", "struct_declaration", "interface_declaration"))
        cls_name = node_text(cls.child_by_field_name("name"), src) if cls is not None and cls.child_by_field_name("name") else None
        if n.type in ("this_expression", "this"):
            return (cls_name, tuple(chain)) if cls_name else None
        if n.type in ("base_expression", "base"):
            if cls is None:
                return None
            bl = next((c for c in cls.children if c.type == "base_list"), None)
            base = next((t for t in (_type_text(c, src) for c in (bl.children if bl is not None else []) if c.is_named) if t), None)
            return (base, tuple(chain)) if base else None
        if n.type == "invocation_expression":                              # provider.GetRequiredService<T>().X()
            resolved = _service_type(n, src)
            return (resolved, tuple(chain)) if resolved else None
        if n.type != "identifier":
            return None
        ident = node_text(n, src)
        local = _scoped_type(ident, call, src)
        if local:
            return (local, tuple(chain))
        if cls is not None and cls_name and ident in _members(cls, src):   # a field/property of the enclosing type
            return (cls_name, (ident, *chain))
        if ident[:1].isupper():
            return (ident, tuple(chain))                                   # static access: `Foo.Bar()` → type Foo
        return (cls_name, (ident, *chain)) if cls_name else None          # inherited member of an in-repo base, maybe

    def call_argument_type(self, call: Node, src: bytes) -> str | None:
        args = call.child_by_field_name("arguments") if call.type == "invocation_expression" else None
        first = next((a for a in (args.children if args is not None else []) if a.type == "argument"), None)
        expr = next((c for c in (first.children if first is not None else []) if c.is_named), None)
        if expr is None:
            return None
        made = _new_type(expr, src)
        if made or expr.type != "identifier":
            return made
        return _scoped_type(node_text(expr, src), call, src, prefer_new=True)

    def message_handlers(self, ctx: ResolveContext, file: FileInfo, message_type: str,
                         handler_bases: frozenset[str]) -> list[str]:
        sent = self._lookup_type(ctx, file, message_type)
        out: list[str] = []
        for fid, facts in ctx.facts.items():
            hf = ctx.files_by_id.get(fid)
            if hf is None or hf.language != self.id:
                continue
            for name, t in (facts.get("types") or {}).items():
                if t["kind"] == "interface":
                    continue
                for base, targs in t.get("generic_bases", []):
                    if base not in handler_bases or not targs:
                        continue
                    handled = self._lookup_type(ctx, hf, targs[0])
                    # both in the repo: same qualified type; both outside (a package's message): same name
                    same = (sent[0] == handled[0]) if sent and handled else (not sent and not handled and targs[0] == message_type)
                    if same:
                        out.append((t["ns"] + "." if t["ns"] else "") + name)
        return sorted(set(out))

    def _lookup_type(self, ctx: ResolveContext, file: FileInfo, simple: str) -> tuple[str, dict[str, Any], FileInfo] | None:
        """(qualified name, facts, declaring file) of a type by simple name, preferring the namespaces
        the caller's file can see (its own namespace, its usings)."""
        hits: list[tuple[str, dict[str, Any], FileInfo]] = []
        for fid, facts in ctx.facts.items():
            t = (facts.get("types") or {}).get(simple)
            f = ctx.files_by_id.get(fid)
            if t is None or f is None or f.language != self.id:
                continue
            hits.append(((t["ns"] + "." if t["ns"] else "") + simple, t, f))
        if not hits:
            return None
        if len(hits) == 1:
            return hits[0]
        mine = ctx.facts.get(file.id) or {}
        visible = set(mine.get("usings") or []) | ({mine.get("file_ns")} if mine.get("file_ns") else set())
        seen = [h for h in hits if h[1]["ns"] in visible]
        return seen[0] if len(seen) == 1 else None

    def resolve_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str, path: tuple[str, ...]) -> str | None:
        cur = self._lookup_type(ctx, file, receiver_type)
        for member in path:
            if cur is None:
                return None
            _, facts, decl_file = cur
            mt = facts["members"].get(member)
            if mt is None:                                   # inherited member: walk the bases declared in this repo
                for b in facts["bases"]:
                    bt = self._lookup_type(ctx, decl_file, b)
                    if bt is not None and member in bt[1]["members"]:
                        mt, decl_file = bt[1]["members"][member], bt[2]
                        break
            cur = self._lookup_type(ctx, decl_file, mt) if mt else None
        return cur[0] if cur else None

    def manifest_deps(self, rel_path: str, text: str) -> tuple[list[str], list[tuple[str, str]]]:
        """.csproj: `<PackageId>` (else `<AssemblyName>`, else the file stem) publishes;
        `<PackageReference Include=".." Version="..">` requires. `<ProjectReference>` is intra-repo."""
        m = _CS_PACKAGE_ID.search(text) or _CS_ASSEMBLY_NAME.search(text)
        name = m.group(1).strip() if m else Path(rel_path).stem
        deps = []
        for ref in _CS_PACKAGE_REF.finditer(text):
            attrs = dict(_CS_ATTR.findall(ref.group(1)))
            inc = attrs.get("Include") or attrs.get("Update")
            if inc:
                deps.append((inc, attrs.get("Version", "")))
        return [name], deps

    def resolve_setup(self, ctx: ResolveContext) -> None:
        impl: dict[str, list[str]] = {}
        for fid, facts in ctx.facts.items():
            f = ctx.files_by_id.get(fid)
            if f is None or f.language != self.id:
                continue
            for name, t in (facts.get("types") or {}).items():
                if t["kind"] == "interface":
                    continue
                q = (t["ns"] + "." if t["ns"] else "") + name
                for b in t["bases"]:
                    impl.setdefault(b, []).append(q)
        ctx.extra["cs_implementers"] = impl

    def supertypes(self, ctx: ResolveContext, qualified_type: str) -> list[str]:
        out: list[str] = []
        seen = {qualified_type}
        queue = [qualified_type]
        while queue:
            q = queue.pop(0)
            simple = q.split(".")[-1]
            for fid, facts in ctx.facts.items():
                t = (facts.get("types") or {}).get(simple)
                f = ctx.files_by_id.get(fid)
                if t is None or f is None or ((t["ns"] + "." if t["ns"] else "") + simple) != q:
                    continue
                for b in t["bases"]:
                    bt = self._lookup_type(ctx, f, b)
                    if bt is not None and bt[0] not in seen:
                        seen.add(bt[0]); out.append(bt[0]); queue.append(bt[0])
        return out

    def has_external_base(self, ctx: ResolveContext, qualified_type: str) -> bool:
        for q in [qualified_type] + self.supertypes(ctx, qualified_type):
            simple = q.split(".")[-1]
            for fid, facts in ctx.facts.items():
                t = (facts.get("types") or {}).get(simple)
                f = ctx.files_by_id.get(fid)
                if t is None or f is None or ((t["ns"] + "." if t["ns"] else "") + simple) != q:
                    continue
                if any(self._lookup_type(ctx, f, b) is None for b in t["bases"]):
                    return True
        return False

    def implementation_target(self, ctx: ResolveContext, qualified_type: str, method: str) -> str | None:
        iface = qualified_type.split(".")[-1]
        impls = sorted(set(ctx.extra.get("cs_implementers", {}).get(iface, [])))
        if len(impls) != 1:
            return None
        impl = impls[0]
        for facts in ctx.facts.values():
            t = (facts.get("types") or {}).get(impl.split(".")[-1])
            if t and ((t["ns"] + "." if t["ns"] else "") + impl.split(".")[-1]) == impl:
                explicit_for = t.get("explicit", {}).get(method)
                if explicit_for and explicit_for != iface:
                    return None          # `IOther.Method` explicit implementation: not what this interface's call reaches
                break
        return impl

    def resolve_import(self, ctx: ResolveContext, file: FileInfo, spec: str, pkg: PackageFactory) -> tuple[str, str] | None:
        files = ctx.namespaces.get(spec)
        if files:
            # one edge per declaring file would explode on big namespaces; point at the first
            # file's module instead, which is the meaningful unit for C#.
            return (ctx.files_by_id[files[0]].module_id, "Module")
        root = spec.split(".")[0]
        return (pkg("nuget", spec, root in FRAMEWORK_ROOTS), "Package")


# Microsoft.Extensions.DependencyInjection: `provider.GetRequiredService<T>()` returns a T
_DI_RESOLVERS = frozenset({"GetRequiredService", "GetService", "GetRequiredKeyedService", "GetKeyedService"})
_CLOSURES = ("lambda_expression", "anonymous_method_expression", "local_function_statement")

_TYPE_NODES = ("identifier", "qualified_name", "generic_name", "nullable_type", "array_type", "predefined_type")
_FUNC_NODES = ("method_declaration", "constructor_declaration", "local_function_statement", "lambda_expression",
               "anonymous_method_expression", "property_declaration", "accessor_declaration")


def _type_text(node: Node | None, src: bytes) -> str | None:
    """`IAccountQuery`, `List<Foo>?` → simple type name (`IAccountQuery`, `List`); None for var/predefined."""
    n = node
    while n is not None and n.type in ("nullable_type", "array_type"):
        n = next((c for c in n.children if c.is_named), None)
    if n is None or n.type in ("implicit_type", "predefined_type"):
        return None
    if n.type == "generic_name":
        n = next((c for c in n.children if c.type == "identifier"), None)
        if n is None:
            return None
    if n.type == "qualified_name":
        return node_text(n, src).split(".")[-1]
    if n.type == "identifier":
        return node_text(n, src)
    return None


def _service_type(expr: Node, src: bytes) -> str | None:
    """`provider.GetRequiredService<T>()` / `GetService<T>()` (DI) → T."""
    if expr.type != "invocation_expression":
        return None
    fn = expr.child_by_field_name("function")
    if fn is not None and fn.type == "member_access_expression":
        fn = fn.child_by_field_name("name")
    if fn is None or fn.type != "generic_name":
        return None
    name = next((c for c in fn.children if c.type == "identifier"), None)
    targs = next((c for c in fn.children if c.type == "type_argument_list"), None)
    if name is None or targs is None or node_text(name, src) not in _DI_RESOLVERS:
        return None
    return _type_text(next((c for c in targs.children if c.is_named), None), src)


def _scoped_type(name: str, at: Node, src: bytes, prefer_new: bool = False) -> str | None:
    """Type of a parameter/local visible at `at`: its own function first, then — from a lambda, anonymous
    method or local function — the functions around it (`.Must(x => repo.NotExists(x))` sees the
    constructor's `var repo`)."""
    scope = _enclosing(at, _FUNC_NODES)
    while scope is not None:
        found = _local_type(name, scope, src, at.start_byte, prefer_new)
        if found or scope.type not in _CLOSURES:
            return found
        scope = _enclosing(scope, _FUNC_NODES)
    return None


def _generic_bases(base_list: Node | None, src: bytes) -> list[tuple[str, list[str]]]:
    """`: ICommandHandler<CreateTodoCommand, CreateTodoResponse?>` → [("ICommandHandler", ["CreateTodoCommand", "CreateTodoResponse"])]."""
    out: list[tuple[str, list[str]]] = []
    for c in (base_list.children if base_list is not None else []):
        g = c
        if g.type == "qualified_name":                     # `Bus.ICommandHandler<X>`
            g = next((x for x in reversed(g.children) if x.is_named), g)
        if g.type != "generic_name":
            continue
        name = next((x for x in g.children if x.type == "identifier"), None)
        targs = next((x for x in g.children if x.type == "type_argument_list"), None)
        if name is None or targs is None:
            continue
        out.append((node_text(name, src), [_type_text(a, src) or "" for a in targs.children if a.is_named]))
    return out


def _new_type(expr: Node, src: bytes) -> str | None:
    """`new T(...)` / `await x` unwrapped → T."""
    n = expr
    while n is not None and n.type in ("await_expression", "parenthesized_expression", "cast_expression"):
        n = next((c for c in n.children if c.is_named and c.type not in _TYPE_NODES), None) if n.type == "cast_expression" \
            else next((c for c in n.children if c.is_named), None)
    if n is not None and n.type == "object_creation_expression":
        return _type_text(n.child_by_field_name("type"), src)
    return None


def _returned_type(expr: Node, scope: Node, src: bytes) -> str | None:
    """`Make(x)` / `this.Make(x)` / `await MakeAsync(x)` → the declared return type of `Make` in the
    enclosing type (`Task<T>` unwrapped when awaited); None for anything else or overloads."""
    awaited = expr.type == "await_expression"
    n = next((c for c in expr.children if c.is_named), None) if awaited else expr
    if n is None or n.type != "invocation_expression":
        return None
    fn = n.child_by_field_name("function")
    if fn is not None and fn.type == "member_access_expression":
        obj = fn.child_by_field_name("expression")
        fn = fn.child_by_field_name("name") if obj is not None and obj.type in ("this_expression", "this") else None
    if fn is None or fn.type != "identifier":
        return None
    owner = _enclosing(scope, ("class_declaration", "record_declaration", "struct_declaration"))
    body = next((c for c in owner.children if c.type == "declaration_list"), None) if owner is not None else None
    name = node_text(fn, src)
    found = [m for m in (body.children if body is not None else [])
             if m.type == "method_declaration" and m.child_by_field_name("name") is not None
             and node_text(m.child_by_field_name("name"), src) == name]
    if len(found) != 1:
        return None
    ret = found[0].child_by_field_name("returns") or found[0].child_by_field_name("type")
    if awaited and ret is not None and ret.type == "generic_name":     # Task<T> / ValueTask<T>
        targs = next((c for c in ret.children if c.type == "type_argument_list"), None)
        ret = next((c for c in targs.children if c.is_named), None) if targs is not None else None
    return _type_text(ret, src)


def _enclosing(node: Node, types: tuple[str, ...]) -> Node | None:
    n = node.parent
    while n is not None and n.type not in types:
        n = n.parent
    return n


def _explicit_impls(type_node: Node, src: bytes) -> dict[str, str]:
    """method name → interface for `Task<X> IFoo.Method(...)` explicit implementations."""
    out: dict[str, str] = {}
    body = next((c for c in type_node.children if c.type == "declaration_list"), None)
    for m in (body.children if body is not None else []):
        if m.type != "method_declaration":
            continue
        spec = next((c for c in m.children if c.type == "explicit_interface_specifier"), None)
        nm = m.child_by_field_name("name")
        if spec is not None and nm is not None:
            iface = node_text(spec, src).rstrip(".").split(".")[-1]
            out[node_text(nm, src)] = iface.split("<")[0]
    return out


def _members(type_node: Node, src: bytes) -> dict[str, str]:
    """Field/property/primary-constructor-parameter name → declared type (simple name)."""
    out: dict[str, str] = {}
    pl = next((c for c in type_node.children if c.type == "parameter_list"), None)
    if pl is not None:
        for prm in pl.children:
            if prm.type == "parameter":
                nm = prm.child_by_field_name("name"); ty = prm.child_by_field_name("type")
                tt = _type_text(ty, src)
                if nm is not None and tt:
                    out[node_text(nm, src)] = tt
    body = next((c for c in type_node.children if c.type == "declaration_list"), None)
    if body is None:
        return out
    for m in body.children:
        if m.type == "field_declaration":
            vd = next((c for c in m.children if c.type == "variable_declaration"), None)
            if vd is None:
                continue
            tt = _type_text(vd.child_by_field_name("type") or next((c for c in vd.children if c.is_named), None), src)
            for d in vd.children:
                if d.type == "variable_declarator" and tt:
                    nm = d.child_by_field_name("name") or next((c for c in d.children if c.type == "identifier"), None)
                    if nm is not None:
                        out[node_text(nm, src)] = tt
        elif m.type == "property_declaration":
            nm = m.child_by_field_name("name"); ty = m.child_by_field_name("type")
            tt = _type_text(ty, src)
            if nm is not None and tt:
                out[node_text(nm, src)] = tt
    return out


def _local_type(name: str, scope: Node, src: bytes, before: int, prefer_new: bool = False) -> str | None:
    """Type of a parameter or local inside `scope` (explicit type, or `new T()` / `var x = new T()`).
    `prefer_new`: the type it was created with wins over the declared one (`IEvent e = new T()` → T)."""
    pl = scope.child_by_field_name("parameters") or next((c for c in scope.children if c.type == "parameter_list"), None)
    if pl is not None:
        for prm in pl.children:
            if prm.type == "parameter":
                nm = prm.child_by_field_name("name")
                if nm is not None and node_text(nm, src) == name:
                    return _type_text(prm.child_by_field_name("type"), src)
    best = None
    for d in walk(scope):
        if d.start_byte >= before:
            break
        if d.type == "variable_declaration" and d.parent is not None and d.parent.type == "local_declaration_statement":
            ty = d.child_by_field_name("type") or next((c for c in d.children if c.is_named), None)
            for v in d.children:
                if v.type != "variable_declarator":
                    continue
                nm = v.child_by_field_name("name") or next((c for c in v.children if c.type == "identifier"), None)
                if nm is None or node_text(nm, src) != name:
                    continue
                tt = _type_text(ty, src)
                if tt is None or prefer_new:
                    init = next((c for c in v.children if c.is_named and c.id != nm.id), None)
                    made = (_new_type(init, src) or _service_type(init, src) or _returned_type(init, scope, src)) if init is not None else None
                    tt = made or tt
                best = tt
    return best


def _ancestors(node: Node):
    n = node.parent
    while n is not None:
        yield n
        n = n.parent


LANGUAGES = [
    CSharpSupport(
        id="csharp", grammar="csharp", extensions=(".cs",), query_file=HERE / "queries.scm", stack="dotnet",
        manifest_suffixes={".csproj": "csproj", ".fsproj": "fsproj"}, builtin_receivers=_BUILTINS, parent_receivers=frozenset({"base"}), ecosystem="nuget",
        http_scanner=CsScanner, namespace_nodes=NAMESPACE_NODES,
        entry_point_hints=("[HttpGet", "[HttpPost", "[HttpPut", "[HttpDelete", "[HttpPatch", "[Route", "IActionResult"),
        decorator_entry=_DECORATOR_ENTRY, dispatch=_MEDIATR,
    ),
]
