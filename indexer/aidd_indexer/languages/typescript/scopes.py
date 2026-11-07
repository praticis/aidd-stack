"""What a name and a `this` in a TS or JS file refer to, as TypeScript's checker resolves them: a name is looked up
from the innermost scope around it outward, and the first scope that binds it in what its place means (a value, a type
or a namespace) gives its declarations; a function's signature sees only its parameters and type parameters, and a
named function or class expression sees its own name after what it binds. What no scope of the file binds may be a
global its `declare global` declares. The scopes and what each binds are `scope_build`'s. A value a function tests with
`instanceof` may be narrowed by the flow, to a class its declaration does not name: the index does not follow the flow,
and tells where it may."""

from __future__ import annotations

from tree_sitter import Node

from ..base import walk
from .scope_build import Builder
from .scope_model import FUNCTIONS, PARAM, TYPE_PARAM, Declared, Frame, Scope

__all__ = ["TsScopes"]

# from a function's signature, a name its first declaration binds there: its parameters' from the parameters and the
# result's type, and its type parameters' from both and from the type parameters
_SEEN = {"signature": (PARAM, TYPE_PARAM), "type-parameters": (TYPE_PARAM,)}


class TsScopes:
    def __init__(self, root: Node, src: bytes) -> None:
        built = Builder(root, src)
        self.src = src
        self._reads, self._thises, self._globals = built.reads, built.thises, built.globals
        self._root, self._tests = root, None

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

    def narrowed(self, written: str, at: int) -> bool:
        """Whether the function around the byte `at` tests the value `written`, or a value that holds it, with
        `instanceof`: the flow may narrow it there. `written` is `spelled`."""
        if self._tests is None:
            self._tests = _tests(self._root, self.src)
        return any(start <= at < end and (written == t or written.startswith(f"{t}.")) for start, end, t in self._tests)

    def thises(self) -> list[Node]:
        return [n for n, _ in self._thises.values()]

    def this_of(self, this: Node) -> Node | None:
        """The node that binds a `this`: a function, a method, a field's initializer, a static block, a namespace, an
        enum, or the file."""
        found = self._thises.get(this.id)
        return found[1] if found is not None else None


def spelled(node: Node | None) -> str:
    """The value an expression writes, without the spaces, the `?.` and the `!` that do not change which it is."""
    text = node.text.decode(errors="replace") if node is not None else ""
    return "".join(text.split()).replace("?", "").replace("!", "")


def _tests(root: Node, src: bytes) -> list[tuple[int, int, str]]:
    """(the span of the function around it, the value written) of each `value instanceof C` of the file."""
    out = []
    for n in walk(root) if b"instanceof" in src else ():
        op = n.child_by_field_name("operator") if n.type == "binary_expression" else None
        if op is not None and op.type == "instanceof":
            around = n.parent
            while around.parent is not None and around.type not in FUNCTIONS:
                around = around.parent
            out.append((around.start_byte, around.end_byte, spelled(n.child_by_field_name("left"))))
    return out


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
