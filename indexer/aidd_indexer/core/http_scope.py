"""Lexical scopes and name bindings in one file, for any parseable language.

A name is looked up from the innermost enclosing function outward, without entering the bodies of other
functions: the closest assignment before the use binds it, and a parameter ends the search (its value is the
caller's). `x += e` binds `x` to the earlier value plus `e`; the assignment that contains the use is never its
binding (`url = `${url}?q``). What no enclosing function binds is a module-level name.
"""

from __future__ import annotations

from tree_sitter import Node

from ..languages.base import node_text as text, walk
from .http_nodes import APPEND_NODES, ASSIGNMENT_NODES, FUNCTION_SCOPES


def enclosing_function(n: Node) -> Node | None:
    p = n.parent
    while p is not None and p.type not in FUNCTION_SCOPES:
        p = p.parent
    return p


def in_function(n: Node) -> bool:
    return enclosing_function(n) is not None


def scope_id(n: Node) -> int:
    """Id of the function around `n`; 0 at module level."""
    f = enclosing_function(n)
    return f.id if f is not None else 0


class _End:
    """A position after every node: `assigned_before(scope, END, name)` asks whether the scope binds `name` at all."""
    start_byte = 1 << 62


END = _End()


class Scopes:
    def __init__(self, root: Node, src: bytes, declarations: frozenset[str] | None = None) -> None:
        """`declarations`: the nodes that declare a name in a function, where a plain assignment does not (Go's `=`
        assigns to the variable it finds, a package's when the function declares none); None: any assignment does."""
        self.root, self.src, self.declarations = root, src, declarations
        self._binds: dict[tuple[int, str], bool] = {}
        self._index: dict[int, dict[str, list[tuple[int, int, bool, Node]]]] = {}

    def binding(self, ident: Node, name: str | None = None) -> tuple[bool, Node | None]:
        """(True, value) for an assignment that precedes the use — `value` is the assignment itself for `x += e` —,
        (True, None) for a parameter, (False, None) when no enclosing function binds the name. Code at module
        level reads the module. `name`: another name, seen from where `ident` is (`u.Path` from a use of `u`)."""
        name = name or text(ident, self.src)
        scope = enclosing_function(ident)
        while scope is not None:
            val = self.assigned_before(scope, ident, name)
            if val is not None:
                return True, val
            if self.is_parameter(scope, name):
                return True, None
            scope = enclosing_function(scope)
        if in_function(ident):
            return False, None
        val = self.assigned_before(self.root, ident, name)
        return val is not None, val

    def binding_scope(self, name: str, at: Node) -> int:
        """Id of the function that binds `name` as seen from `at` (a parameter or a local); 0 for module level."""
        scope = enclosing_function(at)
        while scope is not None:
            key = (scope.id, name)
            if key not in self._binds:
                self._binds[key] = self.is_parameter(scope, name) or (
                    self.assigned_before(scope, END, name) is not None if self.declarations is None
                    else self._declares(scope, name))
            if self._binds[key]:
                return scope.id
            scope = enclosing_function(scope)
        return 0

    def _declares(self, scope: Node, name: str) -> bool:
        """`scope` declares `name` with one of `declarations` (`x := ..`, `var x T`), outside other functions' bodies."""
        stack = [scope]
        while stack:
            d = stack.pop()
            if d is not scope and d.type in FUNCTION_SCOPES:
                continue
            stack.extend(d.children)
            if d.type in self.declarations and not (d.type == "range_clause" and not any(c.type == ":=" for c in d.children)):
                left = d.child_by_field_name("left") or d.child_by_field_name("name")
                names = [c for c in left.children if c.type == "identifier"] if left is not None and left.type == "expression_list" \
                    else [c for c in d.children if c.type == "identifier"] if left is None or d.type == "var_spec" else [left]
                if any(text(c, self.src) == name for c in names):
                    return True
        return False

    def is_parameter(self, scope: Node, name: str) -> bool:
        for field_name in ("parameters", "parameter", "receiver"):
            params = scope.child_by_field_name(field_name)
            if params is not None and any(d.type == "identifier" and text(d, self.src) == name for d in walk(params)):
                return True
        return False

    def assigned_before(self, scope: Node, at, name: str) -> Node | None:
        """Value of the last assignment to `name` before `at` in `scope`, leaving out the bodies of other functions."""
        best: Node | None = None
        for start, end, append, value in self._assignments(scope).get(name, ()):
            if start >= at.start_byte:
                break                            # in document order
            if start <= at.start_byte < end:
                continue                         # `url = `${url}?x``: the name on the right is the earlier value
            if append:
                best = value                     # `url += "/" + id`: read by path_of as the earlier value plus this
            elif best is None or start > best.start_byte:
                best = value
        return best

    def _assignments(self, scope: Node) -> dict[str, list[tuple[int, int, bool, Node]]]:
        """name → (start, end, is `+=`, value) of every assignment in `scope` outside other functions' bodies, in
        document order: read once per scope, so a lookup does not walk the scope again."""
        index = self._index.get(scope.id)
        if index is not None:
            return index
        index = {}
        stack = [scope]
        while stack:
            d = stack.pop()
            if d is not scope and d.type in FUNCTION_SCOPES:
                continue
            stack.extend(reversed(d.children))
            for name, append, value in self._assigned(d):
                index.setdefault(name, []).append((d.start_byte, d.end_byte, append, value))
        self._index[scope.id] = index
        return index

    def _assigned(self, d: Node) -> list[tuple[str, bool, Node]]:
        """The names node `d` assigns: (name, is `+=`, value — the node itself for `+=`)."""
        if d.type in APPEND_NODES:
            op, left = d.child_by_field_name("operator"), d.child_by_field_name("left")
            if op is not None and left is not None and text(op, self.src) == "+=":
                return [(text(left, self.src), True, d)]
        if d.type not in ASSIGNMENT_NODES:
            return []
        left = d.child_by_field_name("left") or d.child_by_field_name("name")
        right = d.child_by_field_name("right") or d.child_by_field_name("value")
        if d.type == "variable_declarator" and right is None:                 # C#
            kids = [c for c in d.children if c.is_named]
            if len(kids) >= 2:
                left, right = kids[0], kids[-1]
                if right.type == "equals_value_clause":
                    inner = [c for c in right.children if c.is_named]
                    right = inner[-1] if inner else right
        if left is None or right is None:
            return []
        lefts = [c for c in left.children if c.is_named] if left.type == "expression_list" else [left]
        rights = [c for c in right.children if c.is_named] if right.type == "expression_list" else [right]
        return [(text(lft, self.src), False, rights[i]) for i, lft in enumerate(lefts) if i < len(rights)]

    def appends_to(self, d: Node, name: str) -> bool:
        """`name += expr` (JS/Python/C# augmented assignment, Go `+=` assignment statement)."""
        if d.type not in APPEND_NODES:
            return False
        op, left = d.child_by_field_name("operator"), d.child_by_field_name("left")
        return op is not None and left is not None and text(op, self.src) == "+=" and text(left, self.src) == name
