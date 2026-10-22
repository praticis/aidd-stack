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

from tree_sitter import Node

from ...core.dispatch import DispatchRule
from ...core.model import FileInfo
from ...core.types import RepoTypes, Unknown
from ...tree import NodeCache
from ..base import LanguageSupport, PackageFactory, ResolveContext, node_text, walk
from .http import CsScanner
from .type_facts import NAMESPACE_NODES, CsTypes, members, namespaces, type_facts, type_text
from .type_index import CsTypeIndex, qualified, ref as type_ref

HERE = Path(__file__).parent

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
        return namespaces(root, src)

    # ---- static receiver types
    def file_facts(self, root: Node, src: bytes) -> CsTypes:
        return type_facts(root, src)

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
            base = next((t for t in (type_text(c, src) for c in (bl.children if bl is not None else []) if c.is_named) if t), None)
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
        if cls is not None and cls_name and ident in members(cls, src):   # a field/property of the enclosing type
            return (cls_name, (ident, *chain))
        if ident[:1].isupper():
            return (ident, tuple(chain))                                   # static access: `Foo.Bar()` → type Foo
        return (cls_name, (ident, *chain)) if cls_name else None          # inherited member of an in-repo base, maybe

    def arity(self, node: Node, src: bytes) -> tuple[int, int | None] | None:
        pl = node.child_by_field_name("parameters") or next((c for c in node.children if c.type == "parameter_list"), None)
        if pl is None:
            return None
        required = optional = 0
        variadic = False
        for prm in pl.children:
            if prm.type == "params":                        # `params int[] rest`: any number more
                variadic = True
            elif prm.type == "parameter":
                if any(m.type == "modifier" and node_text(m, src) == "this" for m in prm.children):
                    continue                                # extension method: the receiver, not an argument
                if any(c.type == "=" for c in prm.children):
                    optional += 1
                else:
                    required += 1
        return (required, None if variadic else required + optional)

    def call_arg_count(self, call: Node, src: bytes) -> int | None:
        args = call.child_by_field_name("arguments")
        if args is None:
            return None
        return sum(1 for a in args.children if a.type == "argument")

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
        return self._types(ctx).handlers(file, message_type, handler_bases)

    def type_index(self, ctx: ResolveContext) -> CsTypeIndex:
        return CsTypeIndex(ctx)

    def _types(self, ctx: ResolveContext) -> CsTypeIndex:
        """The repo's C# type index: the one the HTTP pass shares, or one over this context."""
        if ctx.types is None:
            ctx.types = RepoTypes(ctx)
        return ctx.types.of(self.id)

    def resolve_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str, path: tuple[str, ...]) -> str | None:
        types = self._types(ctx)
        cur = types.type_named(receiver_type, file.path)
        for member in path:
            if isinstance(cur, Unknown):
                return None
            found = types.field(cur, member)
            cur = found.type if not isinstance(found, Unknown) else found
        return qualified(cur) if not isinstance(cur, Unknown) else None

    def external_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str, path: tuple[str, ...],
                          owner: str | None = None) -> str | None:
        """The type the receiver chain ends in is named and no type of this repo has that name: the receiver itself
        (`Substitute`, a `Fixture fixture`) or a member of a repo type (`ILogger _logger`). A name before a path
        (`Company.Shop.Infrastructure.Dependencies`: a namespace), an unknown member (inherited from a base
        outside the repo) or a name two repo types share says nothing."""
        types = self._types(ctx)
        cur = types.type_named(receiver_type, file.path)
        if isinstance(cur, Unknown) and not path and owner:
            # `ParentId.IsEmpty()`: a capitalized name that is not a type may be a member the caller's type inherits —
            # from a base outside the repo too (`HttpContext` of a controller), and then nothing is known
            mt = types.inherited_member_type(owner, receiver_type)
            if mt is not None:
                return mt if mt and not types.is_type_name(mt) else None
        if isinstance(cur, Unknown):
            return receiver_type if not path and not types.is_type_name(receiver_type) else None
        for member in path:
            found = types.field(cur, member)
            if isinstance(found, Unknown):
                return None
            if isinstance(found.type, Unknown):
                return found.written if not types.is_type_name(found.written) else None
            cur = found.type
        return None

    def is_extension_method(self, ctx: ResolveContext, symbol, receiver_type: str | None = None, unknown: bool = False) -> bool:
        """An extension method that can take the receiver: with its type known, one extending that type; with it
        `unknown`, one extending what may be anything — an interface, a type parameter, `object`, a predefined type
        (`this WebApplicationFactory f` takes neither an `HttpClient` nor an unknown receiver)."""
        if symbol.kind != "method" or ctx.files_by_id[symbol.file_id].language != self.id:   # a homonym of another language
            return False
        for name, line, this_type in CsTypes.of(ctx.facts.get(symbol.file_id)).extensions:
            if name == symbol.name and line == symbol.line_start:
                loose = not this_type or this_type == "object" or bool(re.match(r"^I[A-Z]", this_type))
                return loose or this_type == receiver_type if (receiver_type or unknown) else True
        return False

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

    def supertypes(self, ctx: ResolveContext, qualified_type: str) -> list[str]:
        types = self._types(ctx)
        out: list[str] = []
        seen = {qualified_type}
        queue = [qualified_type]
        while queue:
            bases = types.bases(type_ref(queue.pop(0)))
            for b in bases if not isinstance(bases, Unknown) else ():
                if not isinstance(b, Unknown) and qualified(b) not in seen:
                    seen.add(qualified(b)); out.append(qualified(b)); queue.append(qualified(b))
        return out

    def has_external_base(self, ctx: ResolveContext, qualified_type: str) -> bool:
        types = self._types(ctx)
        for q in [qualified_type] + self.supertypes(ctx, qualified_type):
            bases = types.bases(type_ref(q))
            if not isinstance(bases, Unknown) and any(isinstance(b, Unknown) for b in bases):
                return True
        return False

    def implementation_target(self, ctx: ResolveContext, qualified_type: str, method: str,
                              from_type: str | None = None) -> str | None:
        types = self._types(ctx)
        chain = types.di_chain(qualified_type)
        if chain:
            if from_type in chain:                       # a decorator calling the instance it wraps: the next one inward
                i = chain.index(from_type)
                impl = chain[i - 1] if i > 0 else None
            else:
                impl = chain[-1]                         # anyone else gets the outermost
            if impl is None:
                return None
        else:
            impls = types.implementers(type_ref(qualified_type))
            if len(impls) != 1:
                return None
            impl = qualified(impls[0])
        explicit_for = types.explicit_interface(impl, method)
        if explicit_for and explicit_for != type_ref(qualified_type).name:
            return None          # `IOther.Method` explicit implementation: not what this interface's call reaches
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
    return type_text(next((c for c in targs.children if c.is_named), None), src)


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


def _new_type(expr: Node, src: bytes) -> str | None:
    """`new T(...)` / `await x` unwrapped → T."""
    n = expr
    while n is not None and n.type in ("await_expression", "parenthesized_expression", "cast_expression"):
        n = next((c for c in n.children if c.is_named and c.type not in _TYPE_NODES), None) if n.type == "cast_expression" \
            else next((c for c in n.children if c.is_named), None)
    if n is not None and n.type == "object_creation_expression":
        return type_text(n.child_by_field_name("type"), src)
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
    return type_text(ret, src)


def _enclosing(node: Node, types: tuple[str, ...]) -> Node | None:
    n = node.parent
    while n is not None and n.type not in types:
        n = n.parent
    return n


def _local_type(name: str, scope: Node, src: bytes, before: int, prefer_new: bool = False) -> str | None:
    """Type of a parameter or local inside `scope` (explicit type, or `new T()` / `var x = new T()`).
    `prefer_new`: the type it was created with wins over the declared one (`IEvent e = new T()` → T)."""
    pl = scope.child_by_field_name("parameters") or next((c for c in scope.children if c.type == "parameter_list"), None)
    if pl is not None:
        for prm in pl.children:
            if prm.type == "parameter":
                nm = prm.child_by_field_name("name")
                if nm is not None and node_text(nm, src) == name:
                    return type_text(prm.child_by_field_name("type"), src)
    best = None
    for start, ty, v, nm in _LOCALS.get(scope, src).get(name, ()):
        if start >= before:
            break
        tt = type_text(ty, src)
        if tt is None or prefer_new:
            init = next((c for c in v.children if c.is_named and c.id != nm.id), None)
            made = (_new_type(init, src) or _service_type(init, src) or _returned_type(init, scope, src)) if init is not None else None
            tt = made or tt
        best = tt
    return best


def _locals(scope: Node, src: bytes) -> dict[str, list[tuple[int, Node | None, Node, Node]]]:
    """name → (where, its declared type, the declarator, the name) of each local declared under `scope`, in document
    order."""
    out: dict[str, list[tuple[int, Node | None, Node, Node]]] = {}
    for d in walk(scope):
        if d.type == "variable_declaration" and d.parent is not None and d.parent.type == "local_declaration_statement":
            ty = d.child_by_field_name("type") or next((c for c in d.children if c.is_named), None)
            for v in (c for c in d.children if c.type == "variable_declarator"):
                nm = v.child_by_field_name("name") or next((c for c in v.children if c.type == "identifier"), None)
                if nm is not None:
                    out.setdefault(node_text(nm, src), []).append((d.start_byte, ty, v, nm))
    return out


_LOCALS = NodeCache(_locals)


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
