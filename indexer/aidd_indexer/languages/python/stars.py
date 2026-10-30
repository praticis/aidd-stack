"""What a Python star import binds, as CPython does: `from m import *` binds each name of `m`'s `__all__`, or, with
none, each name of `m`'s namespace that does not begin with `_`, those its own star imports bind included. Statements
run in order, so of a module's own binding of a name and a star import that binds it too, the later one holds it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.types import TypeRef, Unknown

if TYPE_CHECKING:
    from .type_facts import Star
    from .type_index import Denoted, Outside

OUTSIDE_STAR = Unknown("a name a star import of a module outside the repo may bind")
UNORDERED = Unknown("a name a function binds that a star import binds too")


class Starred:
    """The star imports of a type index that gives a module's namespace (`_namespace`), its file (`_file_of`), the
    module an import of a file names (`_import`) and a module's member (`_module_member`)."""

    def __init__(self) -> None:
        super().__init__()
        self._exported: dict[TypeRef, frozenset[str] | Unknown] = {}

    def exported(self, module: TypeRef) -> frozenset[str] | Unknown:
        """The names `from module import *` binds."""
        if module not in self._exported:
            self._exported[module] = frozenset()        # a module among its own star imports binds nothing more
            self._exported[module] = self._exports(module)
        return self._exported[module]

    def star_member(self, module: TypeRef, name: str, depth: int) -> Denoted | Outside | Unknown | None:
        """What the star import of `module` that holds `name` last binds it to; None when the module's own binding
        comes after every star import that binds it, or none binds it."""
        ns = self._namespace(module)
        own = (ns.last or {}).get(name) if name in ns.members else -1
        for star in reversed(ns.stars):
            if own is not None and own > star.at:
                return None
            names = self._bound(module, star)
            if isinstance(names, Unknown):
                return names
            if name in names:
                return UNORDERED if own is None else self._module_member(self._source(module, star), name, depth + 1)
        return None

    def _exports(self, module: TypeRef) -> frozenset[str] | Unknown:
        ns = self._namespace(module)
        if ns.exports is not None:
            return ns.exports
        names = {n for n in ns.members if not n.startswith("_")}
        for star in ns.stars:
            found = self._bound(module, star)
            if isinstance(found, Unknown):
                return found
            names |= {n for n in found if not n.startswith("_")}
        return frozenset(names)

    def _bound(self, module: TypeRef, star: Star) -> frozenset[str] | Unknown:
        source = self._source(module, star)
        return source if isinstance(source, Unknown) else self.exported(source)

    def _source(self, module: TypeRef, star: Star) -> TypeRef | Unknown:
        found = self._import(self._file_of(module), star.spec)
        return found if isinstance(found, (TypeRef, Unknown)) else OUTSIDE_STAR
