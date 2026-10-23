"""C#'s one answer to "what type does the code declare for this name here", which the resolver asks to type a call's
receiver and the HTTP scanner to find the client wrapper a call goes through. A name is what its nearest declaration
in scope makes it, as C# scopes names: a local of a block that encloses the use and declares it before it, from the
innermost block out; a parameter of the function; from a lambda or a local function, on to the function around it;
then a member of the enclosing type. A declaration that states no type still hides what is outside it."""

from __future__ import annotations

from tree_sitter import Node

from ...tree import NodeCache
from ..base import node_text
from .type_facts import TYPE_DECLARATIONS, members, namespace_of, namespaces, outer_of, type_text

FUNCTIONS = ("method_declaration", "constructor_declaration", "local_function_statement", "lambda_expression",
             "anonymous_method_expression", "property_declaration", "accessor_declaration")
CLOSURES = ("lambda_expression", "anonymous_method_expression", "local_function_statement")
TYPE_NODES = ("identifier", "qualified_name", "generic_name", "nullable_type", "array_type", "predefined_type")
# Microsoft.Extensions.DependencyInjection: `provider.GetRequiredService<T>()` returns a T
DI_RESOLVERS = frozenset({"GetRequiredService", "GetService", "GetRequiredKeyedService", "GetKeyedService"})
UNTYPED = ""                                # declared, by a declaration that states no type
CLASSES = ("class_declaration", "record_declaration", "struct_declaration")


def receiver_type(call: Node, receiver: Node, src: bytes) -> tuple[str, tuple[str, ...]] | None:
    """The type a call's receiver starts from, as the code writes it, and the members after it:
    `this._query.FindByIdAsync()` → (the enclosing type, ("_query",)). The enclosing type goes by its qualified name,
    so that a type of the same simple name another namespace declares is not taken for it. A capitalized name that is
    no local, parameter or member of the declaration around the call is `name:(the enclosing type).Name`: a member a
    base or another part of the type declares, or a type's name, which only the type service tells apart."""
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
    return _start(call, n, src, tuple(chain))


def _start(call: Node, n: Node, src: bytes, chain: tuple[str, ...]) -> tuple[str, tuple[str, ...]] | None:
    cls = enclosing(call, TYPE_DECLARATIONS)
    owner = qualified_name(cls, src) if cls is not None and cls.child_by_field_name("name") is not None else None
    if n.type in ("this_expression", "this"):
        return (owner, chain) if owner else None
    if n.type in ("base_expression", "base"):
        base = _first_base(cls, src) if cls is not None else None
        return (base, chain) if base else None
    if n.type == "invocation_expression":                              # provider.GetRequiredService<T>().X()
        resolved = service_type(n, src)
        return (resolved, chain) if resolved else None
    if n.type != "identifier":
        return None
    ident = node_text(n, src)
    local = local_type(ident, call, src)
    if local is not None:
        return (local, chain) if local else None
    if owner and ident in members(cls, src):                           # a field/property of the enclosing type
        return (owner, (ident, *chain))
    if ident[:1].isupper():                                            # a member the type inherits, or a type's name
        return (f"name:({owner}).{ident}" if owner else f"name:{ident}", chain)
    return (owner, (ident, *chain)) if owner else None                 # inherited member of an in-repo base, maybe


def read_name(written: str) -> tuple[str | None, str]:
    """`name:(O).X` → ("O", "X"), a capitalized name read inside the type `O`; `name:X` → (None, "X"); any other form
    → (None, itself)."""
    if not written.startswith("name:("):
        return None, written.removeprefix("name:")
    owner, _, name = written[6:].rpartition(").")
    return owner, name


def local_type(name: str, use: Node, src: bytes, prefer_new: bool = False) -> str | None:
    """The type the nearest declaration of `name` in scope at `use` states, or the one its value is created with
    (`prefer_new`: that one wins over a declared interface); UNTYPED for a declaration that states none; None when no
    local or parameter of that name is in scope."""
    a = use.parent
    while a is not None:
        if a.type in ("block", "switch_body"):
            found = _block_local(a, name, use.start_byte, src, prefer_new)
            if found is not None:
                return found
        elif a.type in FUNCTIONS:
            found = _parameter(a, name, src)
            if found is not None or a.type not in CLOSURES:
                return found
        a = a.parent
    return None


def _block_local(block: Node, name: str, before: int, src: bytes, prefer_new: bool) -> str | None:
    found = None
    for start, declaration in _LOCALS.get(block, src).get(name, ()):
        if start >= before:
            break
        found = declaration
    return _declared(*found, block, src, prefer_new) or UNTYPED if found is not None else None


def _declared(typ: Node | None, declarator: Node, name: Node, at: Node, src: bytes, prefer_new: bool) -> str | None:
    tt = type_text(typ, src)
    if tt is None or prefer_new:
        init = next((c for c in declarator.children if c.is_named and c.id != name.id), None)
        made = (new_type(init, src) or service_type(init, src) or returned_type(init, at, src)
                or called(init, src)) if init is not None else None
        tt = made or tt
    return tt


def _parameter(fn: Node, name: str, src: bytes) -> str | None:
    pl = fn.child_by_field_name("parameters") or next((c for c in fn.children if c.type == "parameter_list"), None)
    if pl is not None and pl.type == "implicit_parameter":           # `x => ..`
        return UNTYPED if node_text(pl, src) == name else None
    for prm in (pl.children if pl is not None else ()):
        nm = prm.child_by_field_name("name") if prm.type == "parameter" else None
        if nm is not None and node_text(nm, src) == name:
            return type_text(prm.child_by_field_name("type"), src) or UNTYPED
    return None


def _locals(block: Node, src: bytes) -> dict[str, list[tuple[int, tuple[Node | None, Node, Node]]]]:
    """name → (where, (its declared type, the declarator, the name)) of each local the block's own statements declare,
    in document order. A switch's sections share one scope."""
    statements = [s for sec in block.children if sec.type == "switch_section" for s in sec.children] \
        if block.type == "switch_body" else block.children
    out: dict[str, list[tuple[int, tuple[Node | None, Node, Node]]]] = {}
    for st in statements:
        d = next((c for c in st.children if c.type == "variable_declaration"), None) \
            if st.type == "local_declaration_statement" else None
        ty = (d.child_by_field_name("type") or next((c for c in d.children if c.is_named), None)) if d is not None else None
        for v in (c for c in (d.children if d is not None else ()) if c.type == "variable_declarator"):
            nm = v.child_by_field_name("name") or next((c for c in v.children if c.type == "identifier"), None)
            if nm is not None:
                out.setdefault(node_text(nm, src), []).append((d.start_byte, (ty, v, nm)))
    return out


_LOCALS = NodeCache(_locals)
_FILE_NAMESPACE = NodeCache(lambda root, src: namespaces(root, src)[1])


def qualified_name(type_node: Node, src: bytes) -> str:
    """A type declaration's name as the type facts qualify it: its namespace, block or file-scoped, the types it is
    nested in, and its name."""
    root = type_node
    while root.parent is not None:
        root = root.parent
    ns = namespace_of(type_node, src) or _FILE_NAMESPACE.get(root, src)
    name = node_text(type_node.child_by_field_name("name"), src)
    return ".".join(p for p in (ns, outer_of(type_node, src), name) if p)


def _first_base(cls: Node, src: bytes) -> str | None:
    bl = next((c for c in cls.children if c.type == "base_list"), None)
    return next((t for t in (type_text(c, src) for c in (bl.children if bl is not None else []) if c.is_named) if t),
                None)


def service_type(expr: Node, src: bytes) -> str | None:
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
    if name is None or targs is None or node_text(name, src) not in DI_RESOLVERS:
        return None
    return type_text(next((c for c in targs.children if c.is_named), None), src)


def new_type(expr: Node, src: bytes) -> str | None:
    """`new T(...)` / `await x` unwrapped → T."""
    n = expr
    while n is not None and n.type in ("await_expression", "parenthesized_expression", "cast_expression"):
        n = next((c for c in n.children if c.is_named and c.type not in TYPE_NODES), None) if n.type == "cast_expression" \
            else next((c for c in n.children if c.is_named), None)
    if n is not None and n.type == "object_creation_expression":
        return type_text(n.child_by_field_name("type"), src)
    return None


def returned_type(expr: Node, scope: Node, src: bytes) -> str | None:
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
    owner = enclosing(scope, CLASSES)
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


def called(expr: Node, src: bytes) -> str | None:
    """`factory.Create()` / `await _factory.CreateAsync()` → `call:(Factory).Create` / `call:(the enclosing
    type)._factory.CreateAsync#await`: what the method returns, read across files by the type service."""
    awaited = expr.type == "await_expression"
    n = next((c for c in expr.children if c.is_named), None) if awaited else expr
    fn = n.child_by_field_name("function") if n is not None and n.type == "invocation_expression" else None
    name = fn.child_by_field_name("name") if fn is not None and fn.type == "member_access_expression" else None
    found = receiver_type(n, fn.child_by_field_name("expression"), src) \
        if name is not None and name.type == "identifier" and fn.child_by_field_name("expression") is not None else None
    if found is None:
        return None
    path = "".join(f".{m}" for m in (*found[1], node_text(name, src)))
    return f"call:({found[0]}){path}" + ("#await" if awaited else "")


def enclosing(node: Node, types: tuple[str, ...]) -> Node | None:
    n = node.parent
    while n is not None and n.type not in types:
        n = n.parent
    return n
