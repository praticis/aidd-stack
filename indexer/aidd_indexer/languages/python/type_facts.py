"""Python's type facts of one file: what each name of its module and of each of its classes denotes, and each class's
bases, as the file declares them. A class's names are its body's and the attributes its methods assign on the
instance (`self.x = ...`). The facts hold no tree node, so they travel; the type index reads them across files."""

from __future__ import annotations

from typing import Any, NamedTuple

from tree_sitter import Node

from ...core.types import Unknown
from ..base import node_text
from .declared import agree, instance, site
from .forms import STAR, UNBOUND, Member, path, ref
from .scope_build import NESTED_TARGETS
from .scopes import PyScopes, Scope


class Namespace(NamedTuple):
    bases: tuple[str | Unknown, ...]    # a class's bases, in order, in its module's terms, or why one is not in them;
                                        # a module's, the star import that may bind a name it does not
    members: dict[str, Member]


class PyTypes(NamedTuple):
    namespaces: dict[str, Namespace]    # the module's under "", each class's under its path (`Outer.Inner`)

    @classmethod
    def of(cls, facts: Any) -> PyTypes:
        """A file's facts as Python's: none for a file of another language."""
        return facts if isinstance(facts, PyTypes) else NONE


NONE = PyTypes({})
EMPTY = Namespace((), {})


def type_facts(index: PyScopes) -> PyTypes:
    namespaces = {"": Namespace((STAR,) if index.module.star_import else (), _module_members(index))}
    for scope in index.scopes:
        found = path(index, scope) if scope.kind == "class" else None
        if isinstance(found, str):
            namespaces[found] = Namespace(_bases(index, scope), _class_members(index, scope))
    return PyTypes(namespaces)


def _module_members(index: PyScopes) -> dict[str, Member]:
    """The module's names, with those its functions bind as `global`."""
    sites = {name: list(nodes) for name, nodes in index.module.bindings.items()}
    for scope in index.scopes[1:]:
        for name in scope.globals & scope.bindings.keys():
            sites.setdefault(name, []).extend(scope.bindings[name])
    return _agreed(index, sites)


def _class_members(index: PyScopes, scope: Scope) -> dict[str, Member]:
    body = {name for name in scope.bindings if name not in scope.globals and name not in scope.nonlocals}
    sites = {name: list(scope.bindings[name]) for name in body}
    for method in _methods(scope):
        for name, nodes in _assigned(index, method).items():
            sites.setdefault(name, []).extend(nodes)
    return {name: _on_class(index, member, sites[name]) if name in body else member
            for name, member in _agreed(index, sites).items()}


def _on_class(index: PyScopes, member: Member, sites: list[Node]) -> Member:
    """A value the class body gives a name, with no annotation to say what it reads as: read on an instance or the
    class, it goes through the descriptor protocol."""
    if member.kind != "value" or any((found := site(index, s)) is not None and found[1] for s in sites):
        return member
    return Member("attribute", member.written)


def _agreed(index: PyScopes, sites: dict[str, list[Node]]) -> dict[str, Member]:
    return {name: agree(index, sorted(nodes, key=lambda n: n.start_byte)) for name, nodes in sorted(sites.items())}


def _methods(scope: Scope) -> list[Scope]:
    """The functions a class body defines; a generic one's is inside its type parameters' scope."""
    found = []
    for child in scope.children:
        found += [child] if child.kind == "function" else \
            [c for c in child.children if c.kind == "function"] if child.kind == "annotation" else []
    return [f for f in found if f.node.type == "function_definition"]


def _assigned(index: PyScopes, method: Scope) -> dict[str, list[Node]]:
    """The attributes a method assigns on its instance, `self.x = ...`; none when it binds `self` again."""
    first = instance(index, method)
    name = node_text(first, index.src) if first is not None else ""
    if not name or len(method.bindings.get(name, ())) != 1:
        return {}
    out: dict[str, list[Node]] = {}
    for use in method.uses.get(name, ()):
        attribute = use.parent
        if attribute is not None and attribute.type == "attribute" \
                and attribute.child_by_field_name("object").id == use.id and _target(attribute):
            out.setdefault(node_text(attribute.child_by_field_name("attribute"), index.src), []).append(attribute)
    return out


def _target(node: Node) -> bool:
    """Whether an assignment, an augmented one, a `for` or a `with` binds `node`."""
    while node.parent is not None and node.parent.type in NESTED_TARGETS:
        node = node.parent
    parent = node.parent
    field = TARGET_FIELDS.get(parent.type) if parent is not None else None
    found = parent.child_by_field_name(field) if field is not None else None
    return found is not None and found.id == node.id


TARGET_FIELDS = {"assignment": "left", "augmented_assignment": "left", "for_statement": "left",
                 "for_in_clause": "left", "as_pattern": "alias"}


def _bases(index: PyScopes, scope: Scope) -> tuple[str | Unknown, ...]:
    """The bases a class names, in order; `object`, every class's last base, is left out."""
    args = scope.node.child_by_field_name("superclasses")
    out = []
    for base in args.named_children if args is not None else ():
        if base.type == "keyword_argument":
            continue
        origin = base.child_by_field_name("value") if base.type == "subscript" else base
        found = ref(index, origin)
        if found == UNBOUND and node_text(base, index.src) == "object":
            continue
        out.append(found)
    return tuple(out)
