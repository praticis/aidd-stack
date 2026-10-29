"""What Python's HTTP scanner asks of Python's own scopes and types: the scope a router's name is bound in, as the
resolver reads a name."""

from __future__ import annotations

from tree_sitter import Node

from ...core.http_scope import Scopes
from .scopes import PyScopes


class PyRouterScopes(Scopes):
    """The core's scopes, with the scope that binds a name as Python's compiler has it: a class body does not enclose
    its methods, and `global` and `nonlocal` bind the name in the scope they point to. What an assignment gives a name
    stays the core's. The index is built on the first question: most files register no route."""

    def __init__(self, root: Node, src: bytes) -> None:
        super().__init__(root, src)
        self._python: PyScopes | None = None

    @property
    def python(self) -> PyScopes:
        if self._python is None:
            self._python = PyScopes(self.root, self.src)
        return self._python

    def binding_scope(self, name: str, at: Node) -> int:
        found = self.python.resolve(self.python.scope_of(at), name).scope
        return found.node.id if found is not None and found.kind != "module" else 0


class PyRouters:
    """Python's scanner keys a router, the application included, by the scope Python binds its name in."""

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.scopes = PyRouterScopes(self.fx.tree.root_node, self.src)

    def mark_app(self, name: str, at: Node) -> None:
        self.app_vars.add((self.scopes.binding_scope(name, at), name))

    def is_app(self, name: str, at: Node) -> bool:
        return (self.scopes.binding_scope(name, at), name) in self.app_vars
