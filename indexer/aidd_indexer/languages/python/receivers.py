"""The type of the value a Python method is called on, as `CallInfo.receiver_type` carries it: the type its base
declares, then the attributes that follow it."""

from __future__ import annotations

from tree_sitter import Node

from ...core.types import Unknown
from ..base import node_text
from .declared import name_member, owner
from .forms import (BOUND_IN_A_FUNCTION, FUNCTION, IMPORTED_IN_A_FUNCTION, RECEIVER, SUPER, Member, called, path,
                    ref)
from .scopes import PyScopes


def receiver_of(receiver: Node, index: PyScopes) -> tuple[str, tuple[str, ...]] | Unknown:
    """(the type `receiver`'s base declares, the attributes that follow it), or why it has none."""
    attributes, node = [], receiver
    while node is not None and node.type == "attribute":
        attributes.append(node_text(node.child_by_field_name("attribute"), index.src))
        node = node.child_by_field_name("object")
    written = _base(index, node) if node is not None else RECEIVER
    return written if isinstance(written, Unknown) else (written, tuple(reversed(attributes)))


def _base(index: PyScopes, node: Node) -> str | Unknown:
    if node.type == "identifier":
        return _held(index, node, name_member(index, node))
    if node.type == "call":
        return _super(index, node) if _is_super(index, node) else called(index, node)
    return RECEIVER


def _held(index: PyScopes, identifier: Node, member: Member) -> str | Unknown:
    """The type of the value a name holds: a class or a module is its own namespace."""
    if member.kind in ("class", "value"):
        return member.written
    if member.kind in ("module", "import"):
        found = ref(index, identifier)
        return IMPORTED_IN_A_FUNCTION if found == BOUND_IN_A_FUNCTION else found
    return FUNCTION if member.kind == "function" else Unknown(member.why)


def _is_super(index: PyScopes, call: Node) -> bool:
    function = call.child_by_field_name("function")
    if function is None or function.type != "identifier" or node_text(function, index.src) != "super":
        return False
    binding = index.binding(function)
    return binding is not None and binding.scope is None


def _super(index: PyScopes, call: Node) -> str | Unknown:
    arguments = call.child_by_field_name("arguments")
    cls = owner(index.scope_at(call.child_by_field_name("function")))
    if arguments is not None and arguments.named_children or cls is None:
        return SUPER
    found = path(index, cls)
    return found if isinstance(found, Unknown) else f"super:{found}"
