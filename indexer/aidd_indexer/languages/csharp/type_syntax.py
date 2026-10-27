"""How C# writes a type, read off the tree: the simple name a written type names and the type arguments it passes, and
the type parameters a declaration introduces, each with the one type its constraints say a value of it is."""

from __future__ import annotations

from tree_sitter import Node

from ..base import node_text

GENERIC_DECLARATIONS = ("class_declaration", "record_declaration", "struct_declaration", "interface_declaration",
                        "method_declaration", "local_function_statement")
NOT_TYPES = frozenset({"notnull", "unmanaged", "default"})   # constraints the grammar reads as a type's name
ARRAY = "Array"                                              # what a value of any array type is: `System.Array`


def type_text(node: Node | None, src: bytes) -> str | None:
    """`IAccountQuery`, `List<Foo>?`, `Microsoft.EntityFrameworkCore.DbSet<T>` → simple type name (`IAccountQuery`,
    `List`, `DbSet`); `Array` for `Foo[]`; None for var/predefined."""
    n = _named(node)
    if n is not None and n.type == "array_type":
        return ARRAY
    if n is not None and n.type == "generic_name":
        n = next((c for c in n.children if c.type == "identifier"), None)
    return node_text(n, src) if n is not None and n.type == "identifier" else None


def written_text(node: Node | None, src: bytes) -> str | None:
    """`type_text`, with the simple names of the type arguments a generic type passes: `Holder<HttpService>`, and
    `Map<, List>` for `Map<string, List<Item>>`, a predefined type being no name."""
    n, name = _named(node), type_text(node, src)
    targs = next((c for c in n.children if c.type == "type_argument_list"), None) \
        if name and n is not None and n.type == "generic_name" else None
    return f"{name}<{', '.join(type_text(a, src) or '' for a in targs.children if a.is_named)}>" if targs else name


def type_arity(node: Node | None) -> int:
    """How many type arguments a written type passes: 1 for `ISet<T>`, 0 for `ISet` — C# tells types of one name
    apart by it."""
    n = _named(node)
    targs = next((c for c in n.children if c.type == "type_argument_list"), None) \
        if n is not None and n.type == "generic_name" else None
    return sum(1 for a in targs.children if a.is_named) if targs is not None else 0


def bare(written: str) -> str:
    """A written type without the type arguments `written_text` gives it."""
    return written.partition("<")[0]


def type_arguments(written: str) -> tuple[str, ...]:
    """The type arguments `written_text` gives a type: `Holder<HttpService>` → ("HttpService",)."""
    inner = written.partition("<")[2]
    return tuple(inner[:-1].split(", ")) if inner else ()


def _named(node: Node | None) -> Node | None:
    """The name a written type ends in, past `?` and a namespace; an array is no name of its element."""
    n = node
    while n is not None and n.type == "nullable_type":
        n = next((c for c in n.children if c.is_named), None)
    return n.child_by_field_name("name") if n is not None and n.type == "qualified_name" else n


def type_parameters(n: Node, src: bytes) -> tuple[tuple[str, str], ...]:
    """The type parameters a type or a method declares, in order, each with the simple name of the one type its
    constraints name: "" when they name none, or more than one (`where T : IA, IB`), since a value of it is then
    neither."""
    tps = n.child_by_field_name("type_parameters") \
        or next((c for c in n.children if c.type == "type_parameter_list"), None)
    names = [node_text(c.child_by_field_name("name"), src) for c in (tps.children if tps is not None else ())
             if c.type == "type_parameter" and c.child_by_field_name("name") is not None]
    bounds: dict[str, str] = {}
    for clause in (c for c in n.children if c.type == "type_parameter_constraints_clause"):
        name = next((c for c in clause.children if c.type == "identifier"), None)
        named = [t for c in clause.children if c.type == "type_parameter_constraint"
                 and (t := type_text(c.child_by_field_name("type"), src)) and t not in NOT_TYPES]
        if name is not None:
            bounds[node_text(name, src)] = named[0] if len(named) == 1 else ""
    return tuple((p, bounds.get(p, "")) for p in names)


def bound_in_scope(written: str, at: Node, src: bytes) -> str | None:
    """What a type written at `at` is when it names a type parameter in scope there, the nearest declaration first: the
    one type its constraints name, "" for none; None when it names no type parameter."""
    n: Node | None = at
    while n is not None:
        if n.type in GENERIC_DECLARATIONS:
            found = dict(type_parameters(n, src)).get(written)
            if found is not None:
                return found
        n = n.parent
    return None
