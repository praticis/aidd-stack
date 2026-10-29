"""What a name in a Python file refers to, as the compiler resolves it: a name a scope binds is its own, unless the
scope declares it `global` or `nonlocal`; any other is the nearest function's around it that binds it, never a class
body's, or else the module's. Every binding counts wherever it is in its scope, as in the compiler: the order of the
statements does not. The scopes and what each binds are `scope_build`'s."""

from __future__ import annotations

from typing import NamedTuple

from tree_sitter import Node

from ...tree import walk
from ..base import node_text
from .scope_build import Builder, Scope

__all__ = ["Binding", "PyScopes", "Scope"]


class Binding(NamedTuple):
    kind: str                       # local, global or free
    scope: Scope | None             # the scope the name belongs to; None for a global nothing in the file binds


class PyScopes:
    def __init__(self, root: Node, src: bytes) -> None:
        built = Builder(root, src)
        self.src = src
        self.module, self.scopes, self._at = built.module, built.scopes, built.at
        self.deferred_annotations = built.deferred_annotations
        # a name a function declares `global` and binds is the module's, as one the module binds itself
        self._module_names = set(self.module.bindings).union(*(s.globals & s.bindings.keys() for s in self.scopes))

    def scope_at(self, identifier: Node) -> Scope | None:
        """The scope an identifier is read or bound in; None for a name that is no variable (an attribute's)."""
        return self._at.get(identifier.id)

    def scope_of(self, node: Node) -> Scope:
        """The scope a node is evaluated in: the outermost of its names' scopes, since a scope the node holds is inside
        its own; for a node with no name, the scope around it."""
        found = [self._at[n.id] for n in walk(node) if n.id in self._at]
        if found:
            return min(found, key=_depth)
        return self.scope_of(node.parent) if node.parent is not None else self.module

    def binding(self, identifier: Node) -> Binding | None:
        scope = self.scope_at(identifier)
        return self.resolve(scope, node_text(identifier, self.src)) if scope is not None else None

    def resolve(self, scope: Scope, name: str) -> Binding:
        """What `name` read or bound in `scope` refers to."""
        if name in scope.globals:
            return self._global(name)
        if name in scope.bindings and name not in scope.nonlocals:
            return self._global(name) if scope.kind == "module" else Binding("local", scope)
        s = scope.parent
        while s is not None and s.kind != "module":
            if s.kind != "class" and name in s.globals:
                return self._global(name)
            if s.kind != "class" and name in s.bindings and name not in s.nonlocals:
                return Binding("free", s)
            s = s.parent
        return self._global(name)

    def sites(self, binding: Binding, name: str) -> list[Node]:
        """The nodes that bind the name a binding refers to: those of its scope, and those of the scopes inside it that
        declare it `global` (for the module) or `nonlocal`, in the order of the source."""
        if binding.scope is None:
            return []
        found = list(binding.scope.bindings.get(name, ()))
        for s in self.scopes:
            if s is not binding.scope and name in (s.globals | s.nonlocals) and name in s.bindings \
                    and self.resolve(s, name).scope is binding.scope:
                found += s.bindings[name]
        return sorted(found, key=lambda n: n.start_byte)

    def _global(self, name: str) -> Binding:
        return Binding("global", self.module if name in self._module_names else None)


def _depth(scope: Scope) -> int:
    depth = 0
    while scope.parent is not None:
        scope, depth = scope.parent, depth + 1
    return depth
