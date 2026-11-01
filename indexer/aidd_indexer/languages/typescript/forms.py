"""How a TS or JS type is written for the type index to read across files, in the terms of the file's module: a type's
name as written (`B`, `m.B`: what an annotation or a `new` names), `call:f` (what a call of the function `f` returns)
or `value:x` (the type of the value the module's name `x` holds). What the declarations in sight do not decide is
`Unknown`, with its reason. A type name a type parameter binds reads as its constraint."""

from __future__ import annotations

from collections.abc import Callable

from tree_sitter import Node

from ...core.types import Unknown
from .scope_model import FUNCTIONS

ANY = Unknown("a value of type any")
UNION = Unknown("a union of several types")
INTERSECTION = Unknown("an intersection of several types")
UNCONSTRAINED = Unknown("a type parameter with no constraint")
LOCAL_TYPE = Unknown("a type declared in a function")
NOT_A_REFERENCE = Unknown("a type that names no class or interface")
NOT_A_NAME = Unknown("a name that is not a name or a module's member")
METHOD_RESULT = Unknown("the result of a method call")
VALUE = Unknown("a value that is not a `new`, a call, a name or an `as`")

NULLISH = frozenset({"null", "undefined"})
WRAPPERS = frozenset({"parenthesized_expression", "non_null_expression", "satisfies_expression"})

# the declaration that binds a type name written at a place, or None when the module or another file declares it
Bound = Callable[[Node], "Node | None"]


def of_type(node: Node | None, bound: Bound) -> str | Unknown:
    """The type a type annotation, or the type in it, names."""
    if node is not None and node.type in ("type_annotation", "parenthesized_type"):
        node = node.named_children[-1] if node.named_child_count else None
    if node is None:
        return NOT_A_REFERENCE
    if node.type == "type_identifier":
        return _named(node, bound)
    if node.type == "nested_type_identifier":
        return _text(node)
    if node.type == "generic_type":
        return of_type(node.child_by_field_name("name"), bound)
    if node.type == "union_type":
        return _union(node, bound)
    if node.type == "predefined_type":
        return ANY if _text(node) == "any" else NOT_A_REFERENCE
    return INTERSECTION if node.type == "intersection_type" else NOT_A_REFERENCE


def _named(name: Node, bound: Bound) -> str | Unknown:
    decl = bound(name)
    holder = decl.parent if decl is not None else None
    if holder is not None and holder.type == "type_parameter":
        constraint = holder.child_by_field_name("constraint")
        return of_type(constraint.named_children[-1], bound) if constraint is not None else UNCONSTRAINED
    if decl is not None and in_function(decl):
        return LOCAL_TYPE
    return _text(name)


def _union(node: Node, bound: Bound) -> str | Unknown:
    """A union of one type with `null` or `undefined` is that type, which a call on a value of it reaches."""
    members, stack = [], [node]
    while stack:
        n = stack.pop()
        if n.type == "union_type":
            stack.extend(n.named_children)
        elif _text(n) not in NULLISH:
            members.append(n)
    return of_type(members[0], bound) if len(members) == 1 else UNION


def of_value(node: Node | None, bound: Bound) -> str | Unknown:
    """The type of a value as a module writes it: a `new`, a call of a function, a name, an `as`."""
    while node is not None and node.type in WRAPPERS and node.named_child_count:
        node = node.named_children[0]
    if node is None:
        return VALUE
    if node.type == "as_expression":
        return of_type(node.named_children[-1], bound)
    if node.type == "new_expression":
        return written(node.child_by_field_name("constructor"))
    if node.type == "call_expression":
        found = written(node.child_by_field_name("function"))
        return METHOD_RESULT if found == NOT_A_NAME else found if isinstance(found, Unknown) else f"call:{found}"
    if node.type == "identifier":
        return f"value:{_text(node)}"
    return VALUE


def written(node: Node | None) -> str | Unknown:
    """A name, or a member of one (`m.B`), as written."""
    if node is not None and node.type == "identifier":
        return _text(node)
    obj = node.child_by_field_name("object") if node is not None and node.type == "member_expression" else None
    prop = node.child_by_field_name("property") if obj is not None else None
    return f"{_text(obj)}.{_text(prop)}" if obj is not None and obj.type == "identifier" and prop is not None \
        else NOT_A_NAME


def in_function(node: Node) -> bool:
    """Whether a declaration is inside a function, whose names no other file reads."""
    p = node.parent
    while p is not None:
        if p.type in FUNCTIONS or p.type == "class_static_block":
            return True
        p = p.parent
    return False


def _text(node: Node) -> str:
    return node.text.decode(errors="replace")
