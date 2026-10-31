"""What a C# call that dispatches runs on an instance. On a class's method, the deepest override of its slot in the
instance's class chain: each one says `override` of the one above it, and one that says `new` hides the slot from the
classes below; another of the name and number, which may be an overload, leaves it. On an interface's method, the
method the nearest class that names the interface among its bases, or a class above it, declares, then the overrides of
that one below it. A method matches by its name and its number of parameters: overloads of one name and number may
each run. A static method dispatches nothing."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ...core.hierarchy import Declared
    from ...core.model import SymbolInfo

_MODIFIER = re.compile(r"\b(override|new|static)\b")


def modifiers(m: SymbolInfo) -> set[str]:
    return set(_MODIFIER.findall(m.signature.split("(", 1)[0]))


def dispatched(declared: Declared, instance: str, method: SymbolInfo) -> list[SymbolInfo]:
    owner = declared.by_id.get(method.parent_id or "")
    chain = _chain(declared, instance)
    if owner is None or owner.qualified_name not in chain or "static" in modifiers(method):
        return []
    classes = [q for q in chain if declared.types[q].kind != "interface"]
    if owner.kind == "interface":
        return _implementation(declared, classes, owner.qualified_name, method)
    below = classes[:classes.index(owner.qualified_name)] if owner.qualified_name in classes else []
    return _overrides(declared, below[::-1], method)


def _chain(declared: Declared, q: str) -> list[str]:
    """The type and its bases of the repo, nearest first: a class's base classes in order."""
    chain = [q]
    for t in chain:
        chain += [b for b in declared.bases.get(t, ()) if b not in chain]
    return chain


def _overrides(declared: Declared, down: list[str], slot: SymbolInfo) -> list[SymbolInfo]:
    """`down`: the classes from just below the slot's down to the instance's."""
    found = [slot]
    for q in down:
        here = _same(declared, q, slot)
        overriding = [m for m in here if "override" in modifiers(m)]
        if overriding:
            found = overriding
        elif any("new" in modifiers(m) for m in here):
            break
    return found


def _implementation(declared: Declared, classes: list[str], interface: str, method: SymbolInfo) -> list[SymbolInfo]:
    """The method of the class nearest the instance's that names the interface, or of a class above it, and the
    overrides of it below; the interface's own (a default implementation) when no class declares one."""
    names = [i for i, q in enumerate(classes) if any(interface in _chain(declared, b)
                                                     for b in declared.bases.get(q, ()) if b not in classes)]
    for k in range(names[0], len(classes)) if names else ():
        here = _same(declared, classes[k], method)
        if here:
            return [m for h in here for m in _overrides(declared, classes[:k][::-1], h)]
    return [method]


def _same(declared: Declared, q: str, method: SymbolInfo) -> list[SymbolInfo]:
    """The methods of `q` of the method's name and number of parameters, but static ones."""
    return [m for m in declared.methods.get(q, ())
            if m.name == method.name and _parameters(m, method) and "static" not in modifiers(m)]


def _parameters(a: SymbolInfo, b: SymbolInfo) -> bool:
    return a.arity is None or b.arity is None or a.arity[1] == b.arity[1]
