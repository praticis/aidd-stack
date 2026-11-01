"""What a TS or JS call that dispatches runs on an instance of a class, as JS looks a property up. A field the instance
holds, which a class of its chain declares, is found first, and no method of the graph runs; then the nearest class of
its `extends` chain whose prototype holds the name: an accessor runs no method either, and a method runs its last
declaration with a body there, since the implementation follows its overload signatures. An abstract method puts
nothing on the prototype. A static method, an accessor and a constructor dispatch nothing; past a base the index cannot
see, the method may be the base's."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ...core.types import TypeRef
from .type_index import TsTypeIndex, qualified, ref

if TYPE_CHECKING:  # pragma: no cover
    from ...core.hierarchy import Declared
    from ...core.model import SymbolInfo

ACCESSOR = frozenset({"get", "set"})
_WORD = re.compile(r"[\w$]+")


def dispatched(types: TsTypeIndex, declared: Declared, instance: str, method: SymbolInfo) -> list[SymbolInfo]:
    if method.name == "constructor" or modifiers(method) & (ACCESSOR | {"static"}):
        return []
    chain = _chain(types, declared, instance)
    if any(_holds(types, declared, t, method.name) for t in chain):
        return []
    for t in chain:
        found = _runs(declared, t, method.name)
        if found is not None:
            return [m for m in found if m.parent_id != method.parent_id]
    return []


def modifiers(m: SymbolInfo) -> set[str]:
    """The words the signature writes before the name: `static`, `get`, `set`, `abstract`, `async`, `public`."""
    at = re.search(rf"(?<![\w$#]){re.escape(m.name)}(?![\w$])", m.signature)
    return set(_WORD.findall(m.signature[:at.start()])) if at is not None else set()


def _chain(types: TsTypeIndex, declared: Declared, instance: str) -> list[TypeRef]:
    """The classes of the repo an instance of `instance` looks a property up in, nearest first, up to a base the graph
    cannot tell."""
    out: list[TypeRef] = []
    t = ref(instance)
    while isinstance(t, TypeRef) and _class(declared, t) and t not in out:
        out.append(t)
        t = types.extended(t)
    return out


def _class(declared: Declared, t: TypeRef) -> bool:
    found = declared.types.get(qualified(t))
    return found is not None and found.kind == "class"


def _holds(types: TsTypeIndex, declared: Declared, t: TypeRef, name: str) -> bool:
    """Whether instances of the class `t` hold `name` as their own: a field or a parameter property, not a getter."""
    return types.holds(t, name) and not any(m.name == name and modifiers(m) & ACCESSOR
                                            for m in declared.methods.get(qualified(t), ()))


def _runs(declared: Declared, t: TypeRef, name: str) -> list[SymbolInfo] | None:
    """What the prototype of the class `t` holds under `name`: its implementation, or nothing for an accessor, which
    runs no method; None where it holds nothing."""
    here = [m for m in declared.methods.get(qualified(t), ()) if m.name == name and "static" not in modifiers(m)]
    if any(modifiers(m) & ACCESSOR for m in here):
        return []
    bodies = [m for m in here if "abstract" not in modifiers(m)]
    return [max(bodies, key=lambda m: m.line_start)] if bodies else None
