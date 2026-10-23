"""How C# writes a type, read off the tree: the simple name a written type names, and the type parameters a declaration
introduces, each with the one type its constraints say a value of it is."""

from __future__ import annotations

from tree_sitter import Node

from ..base import node_text

GENERIC_DECLARATIONS = ("class_declaration", "record_declaration", "struct_declaration", "interface_declaration",
                        "method_declaration", "local_function_statement")
NOT_TYPES = frozenset({"notnull", "unmanaged", "default"})   # constraints the grammar reads as a type's name


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
