"""A language's facts of a package directory that its scanner reads across the directory's files. Each field declares
how two files' values for one key join, so the facts come out the same whether each file adds to them in turn or each
file's part is joined later, in file order, from another process."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from functools import cache
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

if TYPE_CHECKING:
    from .http_base import PackageContext

AGREE = "agree"     # one value per key, None once two files give different ones
LAST = "last"       # the later file's value
UNION = "union"     # a set of keys

F = TypeVar("F", bound="PackageFacts")


def joined_by(rule: str) -> Any:
    """A field of facts, with how two files' values join."""
    return field(default_factory=set if rule == UNION else dict, metadata={"join": rule})


@cache
def _rules(cls: type) -> dict[str, str]:
    return {f.name: f.metadata["join"] for f in fields(cls)}


@dataclass
class PackageFacts:
    """Subclassed by each language, under a `key` of its own. A directory's context holds the facts of each language
    whose files added some."""

    key: ClassVar[str] = ""

    @classmethod
    def of(cls: type[F], ctx: PackageContext) -> F:
        """The directory's facts of this kind, made when a file first adds to them."""
        found = ctx.facts.get(cls.key)
        if found is None:
            found = ctx.facts[cls.key] = cls()
        return found

    @classmethod
    def read(cls: type[F], ctx: PackageContext) -> F:
        """The directory's facts of this kind, for reading only: an empty one, not kept, when no file added any."""
        found = ctx.facts.get(cls.key)
        return found if found is not None else cls()

    def put(self, name: str, key: Any, value: Any = None) -> None:
        """Adds one file's `value` for `key` to the field `name`, under the field's rule."""
        rule, values = _rules(type(self))[name], getattr(self, name)
        if rule == UNION:
            values.add(key)
        elif rule == AGREE:
            values[key] = value if values.get(key, value) == value else None
        else:
            values[key] = value

    def join(self, later: PackageFacts) -> None:
        """Adds the facts of files that come after these, as their `put`s would have."""
        for name, rule in _rules(type(self)).items():
            if rule == UNION:
                getattr(self, name).update(getattr(later, name))
                continue
            for key, value in getattr(later, name).items():
                self.put(name, key, value)
