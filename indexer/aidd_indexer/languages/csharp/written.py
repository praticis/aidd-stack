"""The receiver's type as C#'s one answer writes it (`locals.receiver_type`), read through the repo's type index: a
type's name, a capitalized name read inside the caller's type (`name:`), or what a method returns (`call:`)."""

from __future__ import annotations

from ...core.types import TypeRef, Unknown
from .locals import read_name
from .type_index import NOT_A_FILE, CsTypeIndex, ref


def named(types: CsTypeIndex, file: str, written: str) -> tuple[TypeRef | Unknown, str]:
    """A capitalized name: the member the type it is read inside has, with the type it writes; else a type nested in
    that type or a base; else the type named."""
    owner, name = read_name(written)
    member = types.member(owner, name) if owner else None
    if member is not None:
        return member.type, member.written
    inner = types.nested(owner, name) if owner else None
    return (ref(inner) if inner else types.type_named(name, file)), name


def start_of(types: CsTypeIndex | None, file: str, written: str) -> tuple[TypeRef | Unknown, str | None]:
    """The type a receiver's written start gives, and the simple name the code writes for it: a capitalized name's
    member or its own name, or the name of the type found."""
    if written.startswith("name:"):
        return named(types, file, written) if types is not None else (NOT_A_FILE, read_name(written)[1])
    cur = written_type(types, file, written) if types is not None else NOT_A_FILE
    return cur, cur.name if not isinstance(cur, Unknown) else None


def written_type(types: CsTypeIndex, file: str, written: str) -> TypeRef | Unknown:
    """A receiver's type as the one answer writes it: a type's name, a capitalized name (`named`), or
    `call:(R).a.M#await`, what the method `M` returns, called on the member `a` of `R` (awaited)."""
    if written.startswith("name:"):
        return named(types, file, written)[0]
    if not written.startswith("call:("):
        return types.type_named(written, file)
    close = written.rindex(")")
    rest = written[close + 1:]
    names = rest.removesuffix("#await").split(".")[1:]
    cur = written_type(types, file, written[6:close])
    for member in names[:-1]:
        found = types.field(cur, member) if not isinstance(cur, Unknown) else cur
        cur = found.type if not isinstance(found, Unknown) else found
    return cur if isinstance(cur, Unknown) else types.method_result(cur, names[-1], rest.endswith("#await"))
