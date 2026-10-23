"""The receiver's type as C#'s one answer writes it (`locals.receiver_type`), read through the repo's type index: a
type's name, with the type arguments it passes, a capitalized name read inside the caller's type (`name:`), or what a
method returns (`call:`); then the members after it."""

from __future__ import annotations

from ...core.types import TypeRef, Unknown
from .locals import read_name
from .type_index import NOT_A_FILE, Arg, CsTypeIndex, ref
from .type_syntax import bare, type_arguments


def named(types: CsTypeIndex, file: str, written: str) -> tuple[TypeRef | Unknown, str]:
    """A capitalized name: the member the type it is read inside has, with the type it writes; else a type nested in
    that type or a base; else the type named."""
    owner, name = read_name(written)
    member = types.member(owner, name) if owner else None
    if member is not None:
        return member.type, member.written
    inner = types.nested(owner, name) if owner else None
    return (ref(inner) if inner else types.type_named(bare(name), file)), bare(name)


def start_of(types: CsTypeIndex | None, file: str, written: str) -> tuple[TypeRef | Unknown, str | None]:
    """The type a receiver's written start gives, and the simple name the code writes for it: a capitalized name's
    member or its own name, or the name of the type found."""
    if written.startswith("name:"):
        return named(types, file, written) if types is not None else (NOT_A_FILE, read_name(written)[1])
    cur = written_type(types, file, written) if types is not None else NOT_A_FILE
    return cur, cur.name if not isinstance(cur, Unknown) else None


def arguments(types: CsTypeIndex, file: str, written: str) -> tuple[Arg, ...]:
    """The type arguments a receiver's written type passes (`Holder<HttpService>`), read in the caller's file."""
    if written.startswith(("name:", "call:")):
        return ()
    return tuple(types.read(types.file(file), a) for a in type_arguments(written))


def follow(types: CsTypeIndex, cur: TypeRef | Unknown, path: tuple[str, ...] | list[str],
           args: tuple[Arg, ...] = ()) -> TypeRef | Unknown:
    """The type the members `path` end in, from the type `cur`, given the type arguments `args`."""
    for member in path:
        found = types.field(cur, member, args) if not isinstance(cur, Unknown) else cur
        cur, args = (found.type if not isinstance(found, Unknown) else found), ()
    return cur


def member_name(types: CsTypeIndex | None, file: str, written: str, path: tuple[str, ...]) -> str | None:
    """The simple name the code writes for the type a receiver's members end in; None when one of them is unknown."""
    cur, name = start_of(types, file, written)
    args = arguments(types, file, written) if types is not None else ()
    for member in path:
        field = types.field(cur, member, args) if not isinstance(cur, Unknown) else cur
        if isinstance(field, Unknown):
            return None
        name, cur, args = field.written, field.type, ()
    return name


def written_type(types: CsTypeIndex, file: str, written: str) -> TypeRef | Unknown:
    """A receiver's type as the one answer writes it: a type's name, a capitalized name (`named`), or
    `call:(R).a.M#await`, what the method `M` returns, called on the member `a` of `R` (awaited)."""
    if written.startswith("name:"):
        return named(types, file, written)[0]
    if not written.startswith("call:("):
        return types.type_named(bare(written), file)
    close = written.rindex(")")
    rest = written[close + 1:]
    names = rest.removesuffix("#await").split(".")[1:]
    start = written[6:close]
    cur = follow(types, written_type(types, file, start), names[:-1], arguments(types, file, start))
    return cur if isinstance(cur, Unknown) else types.method_result(cur, names[-1], rest.endswith("#await"))
