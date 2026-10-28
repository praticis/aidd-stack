"""What each statement of a Python file binds and reads, and in which scope, as CPython builds its scopes: the
module, a class body, a function or a lambda, a comprehension or a generator expression, and the type parameters of a
definition (with a bound's own). A definition's defaults, decorators and annotations, and a comprehension's first
iterable, are read in the scope around them. An assignment expression inside a comprehension binds in the first scope
around it that is not a comprehension."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from tree_sitter import Node

from ..base import node_text, walk

COMPREHENSIONS = ("list_comprehension", "set_comprehension", "dictionary_comprehension", "generator_expression")
# the nodes inside an assignment's target that hold more targets: `a, (b, *c) = ...`
NESTED_TARGETS = frozenset({"pattern_list", "tuple_pattern", "list_pattern", "list_splat_pattern", "tuple", "list",
                            "parenthesized_expression", "as_pattern_target", "expression_list", "list_splat",
                            "dictionary_splat_pattern"})
PATTERNS = frozenset({"case_pattern", "union_pattern", "list_pattern", "tuple_pattern", "dict_pattern"})
WILDCARD = "_"


@dataclass(eq=False)
class Scope:
    node: Node
    kind: str                       # module, class, function, comprehension or annotation (type parameters)
    parent: Scope | None
    bindings: dict[str, list[Node]] = field(default_factory=dict)      # by the scope's own statements
    uses: dict[str, list[Node]] = field(default_factory=dict)
    globals: set[str] = field(default_factory=set)
    nonlocals: set[str] = field(default_factory=set)
    children: list[Scope] = field(default_factory=list)
    star_import: bool = False       # `from m import *`: a name the module does not bind may come from it


class Builder:
    def __init__(self, root: Node, src: bytes) -> None:
        self.src = src
        self.module = Scope(root, "module", None)
        self.scopes = [self.module]
        self.at: dict[int, Scope] = {}              # an identifier's node id -> the scope it is read or bound in
        self.deferred_annotations = any(c.type == "future_import_statement" and b"annotations" in c.text
                                        for c in root.named_children)
        self._stack: list[tuple[Node, Scope]] = [(c, self.module) for c in root.named_children]
        while self._stack:
            node, scope = self._stack.pop()
            handler = HANDLERS.get(node.type)
            if handler is not None:
                handler(self, node, scope)
            else:
                self._push_all(node.named_children, scope)

    def _open(self, node: Node, kind: str, parent: Scope) -> Scope:
        s = Scope(node, kind, parent)
        parent.children.append(s)
        self.scopes.append(s)
        return s

    def _push(self, node: Node | None, scope: Scope) -> None:
        if node is not None:
            self._stack.append((node, scope))

    def _push_all(self, nodes, scope: Scope, skip: tuple[Node | None, ...] = ()) -> None:
        ids = {n.id for n in skip if n is not None}
        self._stack.extend((n, scope) for n in nodes if n.id not in ids)

    def _bind(self, identifier: Node | None, scope: Scope) -> None:
        if identifier is not None and identifier.type == "identifier":
            scope.bindings.setdefault(node_text(identifier, self.src), []).append(identifier)
            self.at[identifier.id] = scope

    def _use(self, identifier: Node, scope: Scope) -> None:
        scope.uses.setdefault(node_text(identifier, self.src), []).append(identifier)
        self.at[identifier.id] = scope

    def _annotation(self, node: Node | None, scope: Scope) -> None:
        """An annotation is read where it is, unless the module defers annotations: its names then read nothing, but
        each still knows its scope."""
        if node is not None and self.deferred_annotations:
            self.at.update((c.id, scope) for c in walk(node) if c.type == "identifier")
        else:
            self._push(node, scope)

    def _targets(self, node: Node | None, scope: Scope) -> None:
        """Bind the names an assignment's target names; an attribute or a subscript in it is read."""
        if node is None:
            return
        if node.type == "identifier":
            self._bind(node, scope)
        elif node.type in NESTED_TARGETS:
            for c in node.named_children:
                self._targets(c, scope)
        else:
            self._push(node, scope)

    def _type_parameters(self, definition: Node, scope: Scope) -> Scope:
        """The scope of a definition's type parameters (`def f[T]`), where its annotations are read; else `scope`."""
        params = definition.child_by_field_name("type_parameters")
        if params is None:
            return scope
        inner = self._open(params, "annotation", scope)
        for p in params.named_children:
            constrained = next((c for c in p.named_children if c.type == "constrained_type"), None)
            name, bound = constrained.named_children[:2] if constrained is not None else (p, None)
            self._bind(next((c for c in walk(name) if c.type == "identifier"), None), inner)
            if bound is not None:                   # `T: Base`, evaluated lazily in a scope of its own
                self._push(bound, self._open(bound, "annotation", inner))
        return inner


def _function(self: Builder, n: Node, scope: Scope) -> None:
    """A `def` or a `lambda`: its name is bound around it, its defaults read there, its annotations read in the scope
    of its type parameters, and its parameters bound in its own scope."""
    self._bind(n.child_by_field_name("name"), scope)
    outer = self._type_parameters(n, scope)
    inner = self._open(n, "function", outer)
    params = n.child_by_field_name("parameters")
    for p in params.named_children if params is not None else ():
        _parameter(self, p, scope, outer, inner)
    self._annotation(n.child_by_field_name("return_type"), outer)
    self._push(n.child_by_field_name("body"), inner)


def _parameter(self: Builder, p: Node, scope: Scope, outer: Scope, inner: Scope) -> None:
    if p.type == "identifier":
        self._bind(p, inner)
        return
    value, annotation = p.child_by_field_name("value"), p.child_by_field_name("type")
    self._push(value, scope)
    self._annotation(annotation, outer)
    read = {x.id for x in (value, annotation) if x is not None}
    for c in p.named_children:
        if c.id not in read:
            self._targets(c, inner)


def _class(self: Builder, n: Node, scope: Scope) -> None:
    self._bind(n.child_by_field_name("name"), scope)
    outer = self._type_parameters(n, scope)
    self._push(n.child_by_field_name("superclasses"), outer)
    self._push(n.child_by_field_name("body"), self._open(n, "class", outer))


def _comprehension(self: Builder, n: Node, scope: Scope) -> None:
    inner = self._open(n, "comprehension", scope)
    first = True
    for c in n.named_children:
        if c.type == "for_in_clause":
            self._targets(c.child_by_field_name("left"), inner)
            self._push_all(c.children_by_field_name("right"), scope if first else inner)
            first = False
        else:
            self._push(c, inner)


def _assignment_expression(self: Builder, n: Node, scope: Scope) -> None:
    target = scope
    while target.kind == "comprehension" and target.parent is not None:
        target = target.parent
    name = n.child_by_field_name("name")
    self._bind(name, target)
    if target is not scope and name is not None:
        self._use(name, scope)
    self._push(n.child_by_field_name("value"), scope)


def _assignment(self: Builder, n: Node, scope: Scope) -> None:
    """`a = b`, `a: T = b`, `a: T`, `a += b`, and a `for` loop's target."""
    left, annotation = n.child_by_field_name("left"), n.child_by_field_name("type")
    self._targets(left, scope)
    self._annotation(annotation, scope)
    self._push_all(n.named_children, scope, skip=(left, annotation))


def _as_pattern(self: Builder, n: Node, scope: Scope) -> None:
    """`with x as y`, `except E as e`."""
    alias = n.child_by_field_name("alias")
    self._targets(alias, scope)
    self._push_all(n.named_children, scope, skip=(alias,))


def _import(self: Builder, n: Node, scope: Scope) -> None:
    """`import a.b` binds `a`; `import a.b as c` and `from m import x as c` bind `c`; `from m import x` binds `x`."""
    for c in n.children_by_field_name("name"):
        if c.type == "aliased_import":
            self._bind(c.child_by_field_name("alias"), scope)
        elif c.named_children:
            self._bind(c.named_children[0], scope)
    if any(c.type == "wildcard_import" for c in n.named_children):
        scope.star_import = True


def _declaration(self: Builder, n: Node, scope: Scope) -> None:
    names = {node_text(c, self.src) for c in n.named_children if c.type == "identifier"}
    (scope.globals if n.type == "global_statement" else scope.nonlocals).update(names)


def _delete(self: Builder, n: Node, scope: Scope) -> None:
    for c in n.named_children:
        self._targets(c, scope)


def _dotted_name(self: Builder, n: Node, scope: Scope) -> None:
    if n.named_children:
        self._use(n.named_children[0], scope)


def _case_pattern(self: Builder, n: Node, scope: Scope) -> None:
    """A `case` pattern: a bare name captures, a dotted name and a class are read, a keyword names an attribute."""
    stack = [n]
    while stack:
        p = stack.pop()
        named = p.named_children
        if p.type == "dotted_name" and len(named) == 1:
            _capture(self, named[0], scope)
        elif p.type == "dotted_name":
            self._push(p, scope)
        elif p.type == "class_pattern":
            self._push(named[0], scope)
            stack.extend(named[1:])
        elif p.type == "keyword_pattern":
            stack.extend(named[1:])
        elif p.type in ("splat_pattern", "as_pattern"):
            _capture(self, named[-1] if named and named[-1].type == "identifier" else None, scope)
            stack.extend(c for c in named if c.type != "identifier")
        elif p.type in PATTERNS:
            stack.extend(named)
        else:
            self._push(p, scope)


def _capture(self: Builder, identifier: Node | None, scope: Scope) -> None:
    if identifier is not None and node_text(identifier, self.src) != WILDCARD:
        self._bind(identifier, scope)


def _type_alias(self: Builder, n: Node, scope: Scope) -> None:
    """`type X[T] = ...`: `X` is bound around it; its parameters have a scope, and its value one inside that."""
    left = n.child_by_field_name("left")
    if left is None or not left.named_children or left.named_children[0].type not in ("identifier", "generic_type"):
        # the grammar reads `type(x).attr = v` as an alias, its `type` a keyword; CPython reads an assignment
        self._use(n.children[0], scope)
        self._targets(left.named_children[0] if left is not None and left.named_children else None, scope)
        self._push(n.child_by_field_name("right"), scope)
        return
    inside = list(walk(left))
    self._bind(next((c for c in inside if c.type == "identifier"), None), scope)
    params = [c for c in inside if c.type == "type_parameter"]
    outer = self._open(params[0], "annotation", scope) if params else scope
    for p in params:
        self._bind(next((c for c in walk(p) if c.type == "identifier"), None), outer)
    self._push(n.child_by_field_name("right"), self._open(n, "annotation", outer))


HANDLERS: dict[str, Callable[[Builder, Node, Scope], None]] = {
    "identifier": lambda s, n, scope: s._use(n, scope),
    "keyword_argument": lambda s, n, scope: s._push(n.child_by_field_name("value"), scope),
    "attribute": lambda s, n, scope: s._push(n.child_by_field_name("object"), scope),
    "function_definition": _function, "lambda": _function, "class_definition": _class,
    **{k: _comprehension for k in COMPREHENSIONS}, "named_expression": _assignment_expression,
    "assignment": _assignment, "augmented_assignment": _assignment, "for_statement": _assignment,
    "as_pattern": _as_pattern, "import_statement": _import, "import_from_statement": _import,
    "future_import_statement": _import, "global_statement": _declaration, "nonlocal_statement": _declaration,
    "delete_statement": _delete, "dotted_name": _dotted_name, "case_pattern": _case_pattern,
    "type_alias_statement": _type_alias,
}
