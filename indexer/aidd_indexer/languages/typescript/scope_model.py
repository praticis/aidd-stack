"""The pieces of a TS or JS file's scope index: a scope and what it binds, in which of TypeScript's meanings (a value, a
type, a namespace); where a name read at a place is looked up; and what a place is read and declared in."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

from tree_sitter import Node

VALUE, TYPE, NAMESPACE = "value", "type", "namespace"
VALUES, TYPES = frozenset({VALUE}), frozenset({TYPE})
CLASS, NAMESPACES, ALL = frozenset({VALUE, TYPE}), frozenset({VALUE, NAMESPACE}), frozenset({VALUE, TYPE, NAMESPACE})
NAMESPACE_ONLY = frozenset({NAMESPACE})
PARAM, TYPE_PARAM = "param", "type-param"

FUNCTIONS = frozenset({"function_declaration", "function_expression", "generator_function_declaration",
                       "generator_function", "arrow_function", "method_definition", "function_signature",
                       "method_signature", "abstract_method_signature", "call_signature", "construct_signature",
                       "function_type", "constructor_type"})
THIS_FUNCTIONS = frozenset({"function_declaration", "function_expression", "generator_function_declaration",
                            "generator_function", "method_definition"})
CLASSES = frozenset({"class_declaration", "abstract_class_declaration", "class"})
FIELDS = frozenset({"public_field_definition", "field_definition"})
BLOCKS = frozenset({"statement_block", "for_statement", "for_in_statement", "catch_clause", "switch_body"})
PARAMETERS = frozenset({"required_parameter", "optional_parameter"})


class Declared(NamedTuple):
    name: Node
    spaces: frozenset[str]
    kind: str = ""          # param or type-param: seen from the signature of the function that declares it


@dataclass(eq=False)
class Scope:
    node: Node
    bindings: dict[str, list[Declared]] = field(default_factory=dict)
    own: Declared | None = None     # a function or class expression's name, looked up after the scope's bindings


class Frame(NamedTuple):
    scope: Scope
    part: str               # all, signature or type-parameters: which of the scope's bindings a name read there sees
    parent: Frame | None


class Ctx(NamedTuple):
    frame: Frame            # where a name read here is looked up first
    container: Scope        # where a `var`, a function outside strict code, a namespace or an import here is bound
    block: Scope            # where a `let`, a `const`, a class or a type here is bound
    strict: bool
    this: Node              # the node that binds `this` here
    outside: Ctx | None = None      # around the function whose parameters these are: where their decorators are read
    infer: Scope | None = None      # the conditional type an `infer` here belongs to


def fields(node: Node) -> list[tuple[Node, str | None]]:
    """A node's named children, each with its field's name."""
    return [(c, node.field_name_for_child(i)) for i, c in enumerate(node.children) if c.is_named]


def pattern_names(pattern: Node | None) -> list[Node]:
    """The names a declaration's target binds: `x`, `{ a, b: [c], d = 1, ...e }`."""
    if pattern is None:
        return []
    t = pattern.type
    if t in ("identifier", "undefined", "shorthand_property_identifier_pattern"):
        return [pattern]
    if t in PARAMETERS:
        return pattern_names(pattern.child_by_field_name("pattern"))
    if t in ("assignment_pattern", "object_assignment_pattern"):
        return pattern_names(pattern.child_by_field_name("left"))
    if t == "pair_pattern":
        return pattern_names(pattern.child_by_field_name("value"))
    if t in ("object_pattern", "array_pattern", "rest_pattern"):
        return [n for c in pattern.named_children for n in pattern_names(c)]
    return []


def use_strict(block: Node | None) -> bool:
    """Whether a file's or a body's prologue (its leading string statements) says "use strict"."""
    for s in block.named_children if block is not None and block.type in ("program", "statement_block") else ():
        if s.type == "comment":
            continue
        e = s.named_children[0] if s.type == "expression_statement" and s.named_child_count else None
        if e is None or e.type != "string":
            return False
        if e.text[1:-1] == b"use strict":
            return True
    return False
