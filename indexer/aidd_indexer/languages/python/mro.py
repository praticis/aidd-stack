"""A class's MRO, C3's, and what may follow a class in the MRO of an instance: `super()` in a method reaches the class
after the method's class in the MRO of the instance's own class, which a class of the repo may make another than the
method's class's base."""

from __future__ import annotations

from collections import defaultdict

from ...core.types import TypeRef, Unknown

NO_MRO = Unknown("bases CPython cannot order")


class Linearized:
    """The MROs of a type index that gives each class's bases (`_bases`) and the classes of the repo it sees
    (`classes`). An MRO holds the repo's classes and, from the first base outside the repo on, that base."""

    def __init__(self) -> None:
        self._linear: dict[TypeRef, list | Unknown] = {}
        self._after: dict[TypeRef, set] | None = None

    def mro(self, cls: TypeRef) -> list | Unknown:
        if cls not in self._linear:
            self._linear[cls] = NO_MRO              # a class among its own bases has none
            self._linear[cls] = self._c3(cls)
        return self._linear[cls]

    def supertypes(self, cls: TypeRef) -> list[TypeRef]:
        """The repo's classes after `cls` in its MRO, up to the first base outside the repo."""
        found = self.mro(cls) if cls.name else []
        out: list[TypeRef] = []
        for t in found[1:] if not isinstance(found, Unknown) else ():
            if not isinstance(t, TypeRef):
                break
            out.append(t)
        return out

    def outside_base(self, cls: TypeRef) -> bool:
        found = self.mro(cls) if cls.name else []
        return not isinstance(found, Unknown) and any(not isinstance(t, TypeRef) for t in found)

    def following(self, cls: TypeRef) -> set:
        """What follows `cls` in the MRO of each class the index sees that has it; an `Unknown` where such a class's
        MRO is not known."""
        if self._after is None:
            self._after = defaultdict(set)
            for d in self.classes():
                found = self.mro(d)
                pairs = zip(found, found[1:]) if not isinstance(found, Unknown) else \
                    ((a, found) for a in self._ancestors(d))
                for a, b in pairs:
                    self._after[a].add(b)
        return self._after.get(cls, set())

    def _ancestors(self, cls: TypeRef) -> set[TypeRef]:
        seen, todo = set(), [cls]
        while todo:
            for b in self._bases(todo.pop()):
                if isinstance(b, TypeRef) and b not in seen:
                    seen.add(b)
                    todo.append(b)
        return seen

    def _c3(self, cls: TypeRef) -> list | Unknown:
        bases = self._bases(cls)
        heads: list[list] = []
        for base in bases:
            found = self.mro(base) if isinstance(base, TypeRef) else base if isinstance(base, Unknown) else [base]
            if isinstance(found, Unknown):
                return found
            heads.append(found)
        merged = merge(heads + [list(bases)])
        return [cls, *merged] if merged is not None else NO_MRO


def merge(sequences: list[list]) -> list | None:
    """C3's merge: None when the sequences admit no order."""
    pending = [list(s) for s in sequences if s]
    out = []
    while pending:
        head = next((s[0] for s in pending if not any(s[0] in t[1:] for t in pending)), None)
        if head is None:
            return None
        out.append(head)
        pending = [r for r in ([x for x in s if x != head] for s in pending) if r]
    return out
