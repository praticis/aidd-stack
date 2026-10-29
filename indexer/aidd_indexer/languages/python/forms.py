"""How a Python type is written for the type index to read across files, in the terms of the module's namespace:
`m.C` (what the name denotes), `call:m.f` (what a call of it returns) or `super:C` (what follows the class `C` in its
MRO); what the declarations in sight do not decide is `Unknown`, with its reason. A name is read through the binding
CPython's scopes give it, so one bound inside a function is no name of the module."""

from __future__ import annotations

import re
from typing import NamedTuple

from tree_sitter import Node

from ...core.types import Unknown
from ..base import node_text
from .scopes import PyScopes, Scope

DOTTED = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*")

UNBOUND = Unknown("a builtin, or a name no statement of the file binds")
STAR = Unknown("a name only a star import may bind")
BOUND_IN_A_FUNCTION = Unknown("a name bound inside a function, read as a type")
CLASS_IN_A_FUNCTION = Unknown("a class defined in a function")
IMPORTED_IN_A_FUNCTION = Unknown("a name a function imports")
DISAGREE = Unknown("bindings that disagree")
DELETED = Unknown("a name the file only deletes")
NO_ANNOTATION = Unknown("a parameter with no annotation")
COLLECTS = Unknown("a parameter that collects arguments")
NO_RESULT = Unknown("a function that declares no result")
UNPACKED = Unknown("an unpacked target")
AUGMENTED = Unknown("an augmented assignment")
FOR = Unknown("a for target")
COMPREHENSION = Unknown("a comprehension's variable")
WITH = Unknown("a with target")
EXCEPT = Unknown("an except target")
MATCH = Unknown("a match capture")
TYPE_PARAMETER = Unknown("a type parameter or a type alias")
UNION = Unknown("a union of several types")
NOT_A_NAME = Unknown("an expression that is not a name")
NOT_A_CALL = Unknown("a value that is not a call")
METHOD_RESULT = Unknown("the result of a method call")
SUPER = Unknown("super() with arguments, or outside a method")
FUNCTION = Unknown("a function")
RECEIVER = Unknown("a receiver that is not a name, an attribute or a call")
OTHER = Unknown("a binding the table does not read")


class Member(NamedTuple):
    """What a name of a module or of a class denotes, as the file declares it."""
    kind: str           # class, function, module, import, value, attribute (a value a class body gives) or unknown
    written: str        # class: its path in the module; function: its declared result ("" for none); module: the
                        # module imported; import: the module and the name (`app.models:B`); value and attribute:
                        # its declared type
    why: str = ""       # unknown, or a function whose result has no type: the reason


def unknown(why: Unknown) -> Member:
    return Member("unknown", "", why.reason)


def declared(form: str | Unknown) -> Member:
    return unknown(form) if isinstance(form, Unknown) else Member("value", form)


def path(index: PyScopes, scope: Scope | None) -> str | Unknown:
    """The dotted path, in its module, of the class whose body `scope` is ("" for the module)."""
    names: list[str] = []
    while scope is not None and scope.kind != "module":
        if scope.kind == "class":
            names.append(node_text(scope.node.child_by_field_name("name"), index.src))
        elif scope.kind != "annotation":
            return CLASS_IN_A_FUNCTION
        scope = scope.parent
    return ".".join(reversed(names))


def ref(index: PyScopes, node: Node | None) -> str | Unknown:
    """A name, or an attribute of one, in the terms of the module's namespace."""
    parts: list[str] = []
    while node is not None and node.type == "attribute":
        parts.append(node_text(node.child_by_field_name("attribute"), index.src))
        node = node.child_by_field_name("object")
    binding = index.binding(node) if node is not None and node.type == "identifier" else None
    if binding is None:
        return NOT_A_NAME
    if binding.scope is None:
        return STAR if index.module.star_import else UNBOUND
    if binding.scope.kind == "annotation":
        return TYPE_PARAMETER
    if binding.scope.kind not in ("module", "class"):
        return BOUND_IN_A_FUNCTION
    prefix = path(index, binding.scope)
    if isinstance(prefix, Unknown):
        return prefix
    return ".".join([p for p in (prefix, node_text(node, index.src)) if p] + parts[::-1])


def forward_reference(index: PyScopes, node: Node) -> str | Unknown:
    """A forward reference, read in the module's namespace."""
    text = "".join(node_text(c, index.src) for c in node.named_children if c.type == "string_content")
    if not DOTTED.fullmatch(text):
        return NOT_A_NAME
    if index.resolve(index.module, text.split(".")[0]).scope is None:
        return STAR if index.module.star_import else UNBOUND
    return text


def value(index: PyScopes, node: Node | None) -> str | Unknown:
    """The type of an assigned value: what a call returns; `a = b = C()` is the call's."""
    while node is not None and node.type == "assignment":
        node = node.child_by_field_name("right")
    return called(index, node) if node is not None and node.type == "call" else NOT_A_CALL


def called(index: PyScopes, call: Node) -> str | Unknown:
    function = call.child_by_field_name("function")
    found = ref(index, function)
    if found == BOUND_IN_A_FUNCTION and function is not None and function.type == "attribute":
        return METHOD_RESULT
    return found if isinstance(found, Unknown) else f"call:{found}"
