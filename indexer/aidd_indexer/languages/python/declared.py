"""The type a binding of a Python file declares, read from the statement that makes it: an annotation (`C | None`,
`Optional[C]` and `"C"` read as `C`, a generic as its origin), a call of a class or of a function, a class, a function
or an import. The bindings of a name are the ones CPython's scopes give it; an annotation on one of them declares the
name's type, and without one they must all declare the same."""

from __future__ import annotations

from typing import Callable

from tree_sitter import Node

from ...core.types import Unknown
from ..base import node_text
from .forms import (ANY, AUGMENTED, COLLECTS, COMPREHENSION, DELETED, DISAGREE, EXCEPT, FOR, MATCH, NO_ANNOTATION,
                    NO_RESULT, NOT_A_NAME, OTHER, STAR, TYPE_PARAMETER, UNBOUND, UNION, UNPACKED, WITH, Member,
                    declared, forward_reference, path, ref, unknown, value)
from .scope_build import NESTED_TARGETS
from .scopes import PyScopes, Scope

TYPING = ("typing", "typing_extensions")
TYPE_VARIABLES = frozenset({"TypeVar", "ParamSpec", "TypeVarTuple", "NewType"})
TRANSPARENT = frozenset({"parenthesized_expression", "as_pattern_target"})
PARAMETERS = frozenset({"parameters", "lambda_parameters"})


def name_member(index: PyScopes, identifier: Node) -> Member:
    """What the binding a name refers to denotes."""
    binding = index.binding(identifier)
    if binding is None:
        return unknown(OTHER)
    if binding.scope is None:
        return unknown(STAR if index.module.star_import else UNBOUND)
    return agree(index, index.sites(binding, node_text(identifier, index.src)))


def agree(index: PyScopes, sites: list[Node]) -> Member:
    """What a name's bindings declare together: what its annotated ones declare, or else what all of them declare. Two
    definitions are two objects, so they disagree."""
    forms = [f for f in (site(index, s) for s in sites) if f is not None]
    if sum(m.kind in ("class", "function") for m, _ in forms) > 1:
        return unknown(DISAGREE)
    pool = {m for m, annotated in forms if annotated} or {m for m, _ in forms}
    if not pool:
        return unknown(DELETED)
    return pool.pop() if len(pool) == 1 else unknown(DISAGREE)


def site(index: PyScopes, target: Node) -> tuple[Member, bool] | None:
    """What one binding declares, and whether an annotation declares it; None for a `del`, which declares nothing.
    `target` is a name, or an attribute an assignment binds (`self.x = ...`)."""
    node, unpacked = target, False
    while node.parent is not None and node.parent.type in NESTED_TARGETS:
        unpacked |= node.parent.type not in TRANSPARENT
        node = node.parent
    parent = node.parent
    if parent is None:
        return unknown(OTHER), False
    if parent.type == "delete_statement":
        return None
    role = ROLES.get(parent.type, _other)
    return role(index, target, parent, unpacked)


def _parameter(index: PyScopes, target: Node, parent: Node, unpacked: bool) -> tuple[Member, bool]:
    if unpacked:
        return unknown(COLLECTS), False
    annotated = parent.child_by_field_name("type")
    if annotated is not None:
        return declared(annotation(index, annotated)), True
    own = _self(index, target, parent)
    return (declared(own) if own is not None else unknown(NO_ANNOTATION)), False


def _assignment(index: PyScopes, target: Node, parent: Node, unpacked: bool) -> tuple[Member, bool]:
    annotated = parent.child_by_field_name("type")
    if annotated is not None:
        return declared(annotation(index, annotated)), True
    return (unknown(UNPACKED) if unpacked else declared(value(index, parent.child_by_field_name("right")))), False


def _walrus(index: PyScopes, target: Node, parent: Node, unpacked: bool) -> tuple[Member, bool]:
    return declared(value(index, parent.child_by_field_name("value"))), False


def _definition(index: PyScopes, target: Node, parent: Node, unpacked: bool) -> tuple[Member, bool]:
    if parent.type == "class_definition":
        enclosing = path(index, index.scope_at(target))
        name = node_text(target, index.src)
        return (unknown(enclosing) if isinstance(enclosing, Unknown)
                else Member("class", f"{enclosing}.{name}" if enclosing else name)), False
    result = parent.child_by_field_name("return_type")
    form = annotation(index, result) if result is not None else NO_RESULT
    return Member("function", "", form.reason) if isinstance(form, Unknown) else Member("function", form), False


def _imported(index: PyScopes, target: Node, parent: Node, unpacked: bool) -> tuple[Member, bool]:
    """`import a.b` binds the module `a`; `import a.b as c`, the module `a.b`; `from m import x [as c]`, the name `x`
    of the module `m`."""
    statement = parent.parent if parent.type in ("dotted_name", "aliased_import") else None
    if statement is None or statement.type not in ("import_statement", "import_from_statement",
                                                   "future_import_statement"):
        return _other(index, target, parent, unpacked)
    name = parent.child_by_field_name("name") if parent.type == "aliased_import" else parent
    written = node_text(name, index.src) if parent.type == "aliased_import" else node_text(target, index.src)
    if statement.type == "import_statement":
        return Member("module", written), False
    module = statement.child_by_field_name("module_name")
    spec = "".join(node_text(module, index.src).split()) if module is not None else "__future__"
    return Member("import", f"{spec}:{node_text(name, index.src)}"), False


def _as(index: PyScopes, target: Node, parent: Node, unpacked: bool) -> tuple[Member, bool]:
    context = parent.parent.type if parent.parent is not None else ""
    return unknown(WITH if context == "with_item" else EXCEPT if context.startswith("except") else MATCH), False


def _fixed(reason: Unknown) -> Callable[[PyScopes, Node, Node, bool], tuple[Member, bool]]:
    return lambda index, target, parent, unpacked: (unknown(reason), False)


def _other(index: PyScopes, target: Node, parent: Node, unpacked: bool) -> tuple[Member, bool]:
    node = parent
    while node is not None and node.type not in ("case_clause", "block", "module"):
        node = node.parent
    return unknown(MATCH if node is not None and node.type == "case_clause" else OTHER), False


ROLES: dict[str, Callable[[PyScopes, Node, Node, bool], tuple[Member, bool]]] = {
    **dict.fromkeys(("parameters", "lambda_parameters", "typed_parameter", "default_parameter",
                     "typed_default_parameter"), _parameter),
    "assignment": _assignment, "named_expression": _walrus, "as_pattern": _as,
    "function_definition": _definition, "class_definition": _definition,
    "dotted_name": _imported, "aliased_import": _imported,
    "augmented_assignment": _fixed(AUGMENTED), "for_statement": _fixed(FOR), "for_in_clause": _fixed(COMPREHENSION),
    **dict.fromkeys(("type_parameter", "constrained_type", "type", "generic_type"), _fixed(TYPE_PARAMETER)),
}


def annotation(index: PyScopes, node: Node | None) -> str | Unknown:
    if node is not None and node.type == "type":
        node = node.named_children[0] if node.named_children else None
    if node is None:
        return NOT_A_NAME
    if node.type == "string":
        return forward_reference(index, node)
    if node.type in ("identifier", "attribute"):
        return _named(index, node)
    if node.type == "binary_operator" and node_text(node.child_by_field_name("operator"), index.src) == "|":
        return _union(index, _alternatives(node, index.src))
    if node.type in ("generic_type", "subscript"):
        return _generic(index, node)
    return NOT_A_NAME


def _named(index: PyScopes, node: Node) -> str | Unknown:
    """A type by its name: `typing.Any` is any type, and a name a `TypeVar` binds stands for the types it may be."""
    if _typing(index, node) == "Any":
        return ANY
    return TYPE_PARAMETER if node.type == "identifier" and _type_variable(index, node) else ref(index, node)


def _type_variable(index: PyScopes, identifier: Node) -> bool:
    binding = index.binding(identifier)
    sites = index.sites(binding, node_text(identifier, index.src)) if binding is not None else []
    values = [s.parent.child_by_field_name("right") for s in sites if s.parent is not None and s.parent.type == "assignment"]
    return any(v is not None and v.type == "call" and _typing(index, v.child_by_field_name("function")) in TYPE_VARIABLES
               for v in values)


def _alternatives(node: Node, src: bytes) -> list[Node]:
    if node.type == "binary_operator" and node_text(node.child_by_field_name("operator"), src) == "|":
        return _alternatives(node.child_by_field_name("left"), src) + _alternatives(node.child_by_field_name("right"), src)
    return [node]


def _union(index: PyScopes, alternatives: list[Node]) -> str | Unknown:
    """`C | None` and `Union[C, None]` are `C`; a union of several types is none of them."""
    kept = [a for a in alternatives if a.type != "none"]
    if len(kept) > 1:
        return UNION
    return annotation(index, kept[0]) if kept else NOT_A_NAME


def _generic(index: PyScopes, node: Node) -> str | Unknown:
    """`Optional[C]` is `C`; a `Union` is read as one; any other generic is its origin (`list[C]` is a list)."""
    if node.type == "generic_type":
        origin = node.named_children[0]
        args = [t.named_children[0] for p in node.named_children[1:] if p.type == "type_parameter"
                for t in p.named_children if t.named_children]
    else:
        origin, args = node.child_by_field_name("value"), node.children_by_field_name("subscript")
    special = _typing(index, origin)
    if special == "Optional":
        return annotation(index, args[0]) if len(args) == 1 else NOT_A_NAME
    if special == "Union":
        return _union(index, args)
    return annotation(index, origin)


def _typing(index: PyScopes, origin: Node | None) -> str | None:
    """The name of `typing`'s that `origin` refers to, if it refers to one."""
    if origin is not None and origin.type == "identifier":
        member = imports_of(index, origin)
        spec, _, name = member.written.rpartition(":") if member is not None else ("", "", "")
        return name if member is not None and member.kind == "import" and spec in TYPING else None
    base = origin.child_by_field_name("object") if origin is not None and origin.type == "attribute" else None
    member = imports_of(index, base) if base is not None and base.type == "identifier" else None
    if member is not None and member.kind == "module" and member.written in TYPING:
        return node_text(origin.child_by_field_name("attribute"), index.src)
    return None


def imports_of(index: PyScopes, identifier: Node) -> Member | None:
    """What the imports that bind a name import, when only imports bind it. Read apart from what the other forms
    declare: an annotation asks it, and a binding's annotation may name that binding (`def list(self) -> list[str]`)."""
    binding = index.binding(identifier)
    sites = index.sites(binding, node_text(identifier, index.src)) if binding is not None else []
    if not sites or any(s.parent is None or s.parent.type not in ("dotted_name", "aliased_import") for s in sites):
        return None
    found = {_imported(index, s, s.parent, False)[0] for s in sites}
    return found.pop() if len(found) == 1 else None


def owner(scope: Scope | None) -> Scope | None:
    """The class whose method the function `scope` is; None for another function."""
    if scope is None or scope.kind != "function" or scope.node.type != "function_definition":
        return None
    outer = scope.parent
    while outer is not None and outer.kind == "annotation":
        outer = outer.parent
    return outer if outer is not None and outer.kind == "class" else None


def instance(index: PyScopes, method: Scope) -> Node | None:
    """The first parameter of a method that is not static: the instance, or a classmethod's class."""
    params = method.node.child_by_field_name("parameters")
    first = params.named_children[0] if params is not None and params.named_children else None
    if owner(method) is None or first is None or first.type != "identifier" or _static(index, method.node):
        return None
    return first


def _self(index: PyScopes, identifier: Node, parent: Node) -> str | Unknown | None:
    """`self` or `cls` is its method's class; None for another parameter."""
    method = index.scope_at(identifier)
    first = instance(index, method) if parent.type in PARAMETERS and method is not None else None
    return path(index, owner(method)) if first is not None and first.id == identifier.id else None


def _static(index: PyScopes, function: Node) -> bool:
    decorated = function.parent if function.parent is not None and function.parent.type == "decorated_definition" \
        else None
    for d in decorated.named_children if decorated is not None else ():
        name = d.named_children[0] if d.type == "decorator" and d.named_children else None
        if name is not None and name.type == "identifier" and node_text(name, index.src) == "staticmethod":
            binding = index.binding(name)
            return binding is not None and binding.scope is None
    return False
