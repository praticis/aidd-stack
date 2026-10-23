"""C#'s type facts of one file, as the file writes them: its types' namespaces, bases and members, the interfaces it
implements explicitly, its `using`s, the implementations it registers with the DI container and its extension methods.
They hold no tree node, so they travel; the resolver reads them across files."""

from __future__ import annotations

from typing import Any, Iterator, NamedTuple

from tree_sitter import Node

from ..base import node_text, walk

NAMESPACE_NODES = frozenset({"namespace_declaration", "file_scoped_namespace_declaration"})
TYPE_DECLARATIONS = ("class_declaration", "record_declaration", "struct_declaration", "interface_declaration")
# Microsoft.Extensions.DependencyInjection registrations (+ Scrutor's `Decorate`): which implementation the container
# hands out
REGISTRARS = frozenset({"AddScoped", "AddTransient", "AddSingleton", "TryAddScoped", "TryAddTransient",
                        "TryAddSingleton", "AddKeyedScoped", "AddKeyedTransient", "AddKeyedSingleton", "Decorate"})


class CsType(NamedTuple):
    kind: str                                               # class | record | struct | interface
    ns: str | None                                          # its namespace, block or file-scoped
    bases: tuple[str, ...]                                  # the simple names its base list writes
    generic_bases: tuple[tuple[str, tuple[str, ...]], ...]  # `IRequestHandler<X, Y>` → ("IRequestHandler", ("X", "Y"))
    members: dict[str, str]                                 # field, property or primary-constructor parameter → the
                                                            # simple name of its type
    explicit: dict[str, str]                                # method → the interface it implements explicitly
    partial: bool                                           # one part of a type other files may declare more of
    results: dict[str, tuple[str, str]]                     # method → the simple name of the type it returns, and of
                                                            # the one `await` gives; "" for none, or for overloads
                                                            # that declare two
    outer: str = ""                                         # the types it is nested in, outermost first (`A.B`)


class CsTypes(NamedTuple):
    types: dict[str, CsType]                                # simple name → the file's last declaration of it
    usings: tuple[tuple[str | None, str], ...]              # (the block namespace whose declaration holds it, None
                                                            # for the file's own; the namespace it imports)
    file_ns: str | None                                     # a file-scoped namespace
    registrations: tuple[tuple[str, tuple[str, str]], ...]  # (`AddScoped`, `Decorate`.., (interface, implementation))
    extensions: tuple[tuple[str, int, str | None, str], ...]  # (name, line, the simple name of the type it extends,
                                                              # and what a value of a repo type must be to pass as its
                                                              # `this`: that name, "object" for any, "" for none)
    namespaces: tuple[str, ...] = ()                        # every namespace the file declares, block or file-scoped

    @classmethod
    def of(cls, facts: Any) -> CsTypes:
        """A file's facts as C#'s: none for a file of another language, or one that did not parse."""
        return facts if isinstance(facts, CsTypes) else NONE


NONE = CsTypes({}, (), None, (), ())


def type_facts(root: Node, src: bytes) -> CsTypes:
    declared, file_ns = namespaces(root, src)
    types: dict[str, CsType] = {}
    usings: list[tuple[str | None, str]] = []
    for n in walk(root):
        if n.type == "using_directive":
            q = next((c for c in n.children if c.type in ("qualified_name", "identifier")), None)
            if q is not None:
                usings.append((namespace_of(n, src), node_text(q, src)))
        elif n.type in TYPE_DECLARATIONS and n.child_by_field_name("name") is not None:
            types[node_text(n.child_by_field_name("name"), src)] = _type(n, src, file_ns)
    registrations = tuple(r for r in (_registration(n, src) for n in walk(root)) if r is not None)
    return CsTypes(types, tuple(usings), file_ns, registrations, _extension_methods(root, src), tuple(declared))


def scopes(facts: CsTypes) -> Iterator[set[str | None]]:
    """Where C# looks for a type's simple name from a file, in order: the namespace the code is in, then each one around
    it out to the global namespace, each followed by the `using`s its declaration holds; the file's own `using`s come
    last. A file that declares more than one namespace looks in all of them at each step out."""
    parts = [ns.split(".") for ns in facts.namespaces]
    for out in range(max(map(len, parts), default=0)):
        here = {".".join(p[:len(p) - out]) for p in parts if len(p) > out}
        yield here
        yield {u for holder, u in facts.usings if holder in here}
    yield {None}
    yield {u for holder, u in facts.usings if holder is None}


def namespaces(root: Node, src: bytes) -> tuple[list[str], str | None]:
    """Every namespace the file declares, and its file-scoped one."""
    found: list[str] = []
    file_ns: str | None = None
    for n in walk(root):
        nm = n.child_by_field_name("name") if n.type in NAMESPACE_NODES else None
        if nm is not None:
            found.append(node_text(nm, src))
            if n.type == "file_scoped_namespace_declaration":
                file_ns = node_text(nm, src)
    return found, file_ns


def type_text(node: Node | None, src: bytes) -> str | None:
    """`IAccountQuery`, `List<Foo>?`, `Microsoft.EntityFrameworkCore.DbSet<T>` → simple type name (`IAccountQuery`,
    `List`, `DbSet`); None for var/predefined."""
    n = node
    while n is not None and n.type in ("nullable_type", "array_type"):
        n = next((c for c in n.children if c.is_named), None)
    if n is not None and n.type == "qualified_name":
        n = n.child_by_field_name("name")
    if n is not None and n.type == "generic_name":
        n = next((c for c in n.children if c.type == "identifier"), None)
    return node_text(n, src) if n is not None and n.type == "identifier" else None


def members(type_node: Node, src: bytes) -> dict[str, str]:
    """Field/property/primary-constructor-parameter name → declared type (simple name); "" for one of the type's own
    type parameters, which declares no type."""
    out: dict[str, str] = {}
    pl = next((c for c in type_node.children if c.type == "parameter_list"), None)
    for prm in (pl.children if pl is not None else []):
        if prm.type == "parameter":
            _declare(out, prm.child_by_field_name("name"), prm.child_by_field_name("type"), src)
    body = next((c for c in type_node.children if c.type == "declaration_list"), None)
    for m in (body.children if body is not None else []):
        if m.type == "field_declaration":
            _fields(out, m, src)
        elif m.type == "property_declaration":
            _declare(out, m.child_by_field_name("name"), m.child_by_field_name("type"), src)
    own = _type_parameters(type_node, src)
    return {name: "" if t in own else t for name, t in out.items()}


def _type_parameters(n: Node, src: bytes) -> set[str]:
    tps = n.child_by_field_name("type_parameters") \
        or next((c for c in n.children if c.type == "type_parameter_list"), None)
    return {node_text(c, src) for c in walk(tps) if c.type == "identifier"} if tps is not None else set()


def _declare(out: dict[str, str], name: Node | None, typ: Node | None, src: bytes) -> None:
    tt = type_text(typ, src)
    if name is not None and tt:
        out[node_text(name, src)] = tt


def _fields(out: dict[str, str], field: Node, src: bytes) -> None:
    vd = next((c for c in field.children if c.type == "variable_declaration"), None)
    if vd is None:
        return
    tt = type_text(vd.child_by_field_name("type") or next((c for c in vd.children if c.is_named), None), src)
    for d in vd.children:
        if d.type == "variable_declarator" and tt:
            nm = d.child_by_field_name("name") or next((c for c in d.children if c.type == "identifier"), None)
            if nm is not None:
                out[node_text(nm, src)] = tt


def _type(n: Node, src: bytes, file_ns: str | None) -> CsType:
    bl = next((c for c in n.children if c.type == "base_list"), None)
    bases = tuple(t for t in (type_text(c, src) for c in (bl.children if bl is not None else [])
                              if c.is_named and c.type != "argument_list") if t)
    # a file-scoped namespace: its declarations are siblings of it, not children
    partial = any(c.type == "modifier" and node_text(c, src) == "partial" for c in n.children)
    return CsType(n.type.split("_")[0], namespace_of(n, src) or file_ns, bases, _generic_bases(bl, src),
                  members(n, src), _explicit_impls(n, src), partial, _results(n, src), _outer(n, src))


def _outer(n: Node, src: bytes) -> str:
    """The types a declaration is nested in, outermost first: `Constants.Conventions` for its `Content`."""
    names: list[str] = []
    a = n.parent
    while a is not None and a.type not in NAMESPACE_NODES:
        if a.type in TYPE_DECLARATIONS and a.child_by_field_name("name") is not None:
            names.insert(0, node_text(a.child_by_field_name("name"), src))
        a = a.parent
    return ".".join(names)


def namespace_of(n: Node, src: bytes) -> str | None:
    """The block namespace a declaration is in; None in a file-scoped one, or in none."""
    a = n.parent
    while a is not None and a.type not in NAMESPACE_NODES:
        a = a.parent
    nm = a.child_by_field_name("name") if a is not None else None
    return node_text(nm, src) if nm is not None else None


def _registration(n: Node, src: bytes) -> tuple[str, tuple[str, str]] | None:
    """`services.AddScoped<I, Impl>()` / `Decorate<I, D>()` → ("AddScoped", ("I", "Impl"))."""
    fn = n.child_by_field_name("function") if n.type == "invocation_expression" else None
    fn = fn.child_by_field_name("name") if fn is not None and fn.type == "member_access_expression" else fn
    if fn is None or fn.type != "generic_name":
        return None
    name = next((c for c in fn.children if c.type == "identifier"), None)
    targs = next((c for c in fn.children if c.type == "type_argument_list"), None)
    if name is None or targs is None or node_text(name, src) not in REGISTRARS:
        return None
    args = [type_text(a, src) or "" for a in targs.children if a.is_named]
    return (node_text(name, src), (args[0], args[1])) if len(args) == 2 and all(args) else None


def _generic_bases(base_list: Node | None, src: bytes) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """`: ICommandHandler<CreateTodoCommand, CreateTodoResponse?>` →
    (("ICommandHandler", ("CreateTodoCommand", "CreateTodoResponse")),)."""
    out: list[tuple[str, tuple[str, ...]]] = []
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
        out.append((node_text(name, src), tuple(type_text(a, src) or "" for a in targs.children if a.is_named)))
    return tuple(out)


def _results(type_node: Node, src: bytes) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    body = next((c for c in type_node.children if c.type == "declaration_list"), None)
    for m in (body.children if body is not None else []):
        name = m.child_by_field_name("name") if m.type == "method_declaration" else None
        if name is not None:
            ret = m.child_by_field_name("returns") or m.child_by_field_name("type")
            found = (type_text(ret, src) or "", _awaited(ret, src) or "")
            out[node_text(name, src)] = found if out.get(node_text(name, src), found) == found else ("", "")
    return out


def _awaited(ret: Node | None, src: bytes) -> str | None:
    """`Task<T>` / `ValueTask<T>` → T: what `await` gives."""
    if ret is None or ret.type != "generic_name" or type_text(ret, src) not in ("Task", "ValueTask"):
        return None
    targs = next((c for c in ret.children if c.type == "type_argument_list"), None)
    return type_text(next((c for c in targs.children if c.is_named), None), src) if targs is not None else None


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


def _extension_methods(root: Node, src: bytes) -> tuple[tuple[str, int, str | None, str], ...]:
    """(name, line, the type it extends, what a value of a repo type must be to pass) of every extension method: the
    first parameter carries `this` — after attributes, over lines (`static bool IsNullOrEmpty([NotNullWhen(false)] this
    Guid? g)`). The type is its simple name, None for a predefined type or one of the method's type parameters."""
    out = []
    for n in walk(root):
        if n.type != "method_declaration" or n.child_by_field_name("name") is None:
            continue
        pl = n.child_by_field_name("parameters")
        first = next((c for c in pl.children if c.type == "parameter"), None) if pl is not None else None
        if first is not None and any(node_text(c, src) == "this" for c in first.children if c.type != "attribute_list"):
            own = _type_parameters(n, src)
            t = type_text(first.child_by_field_name("type"), src)
            out.append((node_text(n.child_by_field_name("name"), src), n.start_point[0] + 1, None if t in own else t,
                        _passes(first.child_by_field_name("type"), src, own)))
    return tuple(out)


def _passes(t: Node | None, src: bytes, own: set[str]) -> str:
    """What a value of a type of the repo must be to pass as a `this` of type `t`: the simple name of the type `t`
    names; "object" when any value passes (`object`, one of the method's type parameters); "" when none does (an array,
    another predefined type)."""
    n = next((c for c in t.children if c.is_named), None) if t is not None and t.type == "nullable_type" else t
    if n is not None and n.type == "predefined_type":
        return "object" if node_text(n, src) == "object" else ""
    name = type_text(n, src) if n is not None and n.type != "array_type" else None
    return "object" if name in own else name or ""
