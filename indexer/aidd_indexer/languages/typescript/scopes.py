"""What a name and a `this` in a TS or JS file refer to, as TypeScript's checker resolves them: a name is looked up
from the innermost scope around it outward, and the first scope that binds it in what its place means (a value, a type
or a namespace) gives its declarations; a function's signature sees only its parameters and type parameters, and a
named function or class expression sees its own name after what it binds. What no scope of the file binds may be a
global its `declare global` declares. The scopes and what each binds are `scope_build`'s."""

from __future__ import annotations

from tree_sitter import Node

from .scope_build import Builder
from .scope_model import PARAM, TYPE_PARAM, Declared, Frame, Scope

__all__ = ["TsScopes"]

# from a function's signature, a name its first declaration binds there: its parameters' from the parameters and the
# result's type, and its type parameters' from both and from the type parameters
_SEEN = {"signature": (PARAM, TYPE_PARAM), "type-parameters": (TYPE_PARAM,)}


class TsScopes:
    def __init__(self, root: Node, src: bytes) -> None:
        built = Builder(root, src)
        self.src = src
        self._reads, self._thises, self._globals = built.reads, built.thises, built.globals

    def names(self) -> list[Node]:
        """The names the file reads through its scopes, as opposed to a declaration's own name or a member's."""
        return [n for n, _, _ in self._reads.values()]

    def binding(self, name: Node) -> list[Node]:
        """The names of the declarations of the file that a name read binds to; none for a name the file does not
        declare, or that is no name read through the scopes."""
        found = self._reads.get(name.id)
        if found is None:
            return []
        _, frame, space = found
        text = name.text.decode(errors="replace")
        while frame is not None:
            decls = _find(frame, text, space)
            if decls:
                return decls
            frame = frame.parent
        return _find(Frame(self._globals, "all", None), text, space)

    def thises(self) -> list[Node]:
        return [n for n, _ in self._thises.values()]

    def this_of(self, this: Node) -> Node | None:
        """The node that binds a `this`: a function, a method, a field's initializer, a static block, a namespace, an
        enum, or the file."""
        found = self._thises.get(this.id)
        return found[1] if found is not None else None


def _find(frame: Frame, name: str, space: str | None) -> list[Node]:
    scope: Scope = frame.scope
    decls = scope.bindings.get(name)
    if decls and (frame.part == "all" or decls[0].kind in _SEEN[frame.part]):
        found = [d.name for d in decls if space is None or space in d.spaces]
        if found:
            return found
    own: Declared | None = scope.own
    if own is not None and own.name.text.decode(errors="replace") == name and (space is None or space in own.spaces):
        return [own.name]
    return []
