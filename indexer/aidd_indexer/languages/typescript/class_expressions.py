"""A class a module declares by an expression is the class of the name that gives it one: the binding of `const X =
class {..}`, the own name of `module.exports = class X {..}`, the property of `exports.X = class {..}`. A class
expression with no such name binds nothing."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tree_sitter import Node

from .commonjs import OWN, text


def bound(facts: Any, name: str, value: Node, owner_of: Callable[[Node], Any]) -> str:
    """Record the class `value` that the module's declaration binds to `name`; the name."""
    facts.owners[name] = owner_of(value)
    return name


def exported(facts: Any, name: str, value: Node, owner_of: Callable[[Node], Any]) -> str | None:
    """Record the class `value` that the module exports as `name` (`OWN` for its own value) under the name it has,
    which is its own for the module's own value and the property's else; None where it has none."""
    local = text(value.child_by_field_name("name")) if name == OWN else name
    if local:
        facts.owners[local] = owner_of(value)
    return local or None
