"""TS's and JS's answers to the type questions across files, from every TS and JS file's type facts: one index for the
three languages, whose files import one another. A type is its file's path without the extension (`app/models`) and its
name there, "" for the module itself. A name is looked up among its module's names, then through what the module imports
and exports; a class's or an interface's members among its own, then its bases', in order. What a package declares is
`Outside`: none of the repo's methods is its."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING, NamedTuple

from ...core.types import Field, TypeIndex, TypeRef, Unknown
from .modules import Package, module_target
from .type_facts import Member, Owner, TsTypes

if TYPE_CHECKING:
    from ..base import ResolveContext

FAMILY = frozenset({"typescript", "tsx", "javascript"})
DEPTH = 16                          # names followed through imports, exports and aliases, at most

OUTSIDE = Unknown("a type a package declares")
NO_FILE = Unknown("an import of no file of the repo")
NOT_A_FILE = Unknown("not a TS or JS file of the repo")
NO_MEMBER = Unknown("its module declares or exports no such name")
NOT_A_TYPE = Unknown("a name that is not a class or an interface")
NOT_CALLABLE = Unknown("a call of what is not a function")
FUNCTION = Unknown("a function, not a value of a class")
CLASS_ITSELF = Unknown("a class itself, whose static side the index does not type")
ENUM = Unknown("an enum or a namespace")
NO_FIELD = Unknown("no class or interface of its bases declares the field")
NO_METHOD = Unknown("no class or interface of its bases declares the method")
BASE_OUTSIDE = Unknown("a member a base outside the repo may give")
ONE_RESULT = Unknown("a TS function returns one value")
TOO_DEEP = Unknown("a chain of names longer than the index follows")


class Outside(NamedTuple):
    """What a package declares, as the repo imports it (`axios`, `some-package`)."""
    name: str


class Denoted(NamedTuple):
    """What a module's name denotes: a member of the file at `file`, or the module itself (`member` None)."""
    file: str
    name: str
    member: Member | None


Found = Denoted | Outside | Unknown
Typed = TypeRef | Outside | Unknown


def typed(types: TsTypeIndex, file: str, written: str, path: tuple[str, ...]) -> Typed:
    """The type of a receiver as the file at path `file` writes it, then of the members `path` names. A type a package
    declares only where the chain ends in it: a member of one may hold a value of the repo."""
    found = types.value(written, file)
    for name in path:
        if isinstance(found, Outside):
            return OUTSIDE
        if not isinstance(found, TypeRef):
            return found
        found = types.attribute(found, name)
    return found


def module_of(path: str) -> str:
    return str(PurePosixPath(path).with_suffix(""))


def qualified(t: TypeRef) -> str:
    return f"{t.package}:{t.name}" if t.name else t.package


def ref(qualified_type: str) -> TypeRef:
    package, _, name = qualified_type.partition(":")
    return TypeRef(package, name)


class TsTypeIndex(TypeIndex):
    def __init__(self, ctx: ResolveContext) -> None:
        self._ctx = ctx
        self._facts = {f.path: TsTypes.of(ctx.facts.get(f.id)) for f in ctx.files_by_path.values()
                       if f.language in FAMILY}
        self._files = {module_of(path): path for path in self._facts}
        self._targets: dict[tuple[str, str], str | Outside | Unknown] = {}

    # -- the type service's questions ------------------------------------------------------------------------------

    def type_named(self, written: str, file: str) -> TypeRef | Unknown:
        return _public(self.value(written, file))

    def return_type(self, function: str, file: str, result: int = 0) -> TypeRef | Unknown:
        return _public(self.value(f"call:{function}", file)) if result == 0 else ONE_RESULT

    def method_return_type(self, owner: TypeRef, method: str, result: int = 0) -> TypeRef | Unknown:
        if result != 0:
            return ONE_RESULT
        found = self._lookup(owner, method, "methods", NO_METHOD, 0)
        return found if isinstance(found, Unknown) else _public(self._called(self._declared(*found), 0))

    def field(self, owner: TypeRef, name: str) -> Field | Unknown:
        found = self._lookup(owner, name, "fields", NO_FIELD, 0)
        if isinstance(found, Unknown):
            return found
        held = self._held(self._declared(*found), 0)
        return Field(_public(held), found[1].written, found[0] != owner)

    def method(self, owner: TypeRef, name: str) -> TypeRef | Unknown:
        found = self._lookup(owner, name, "methods", NO_METHOD, 0)
        return found if isinstance(found, Unknown) else found[0]

    def bases(self, of: TypeRef) -> list[TypeRef | Unknown] | Unknown:
        owner = self._owner(of)
        return NOT_A_TYPE if owner is None else [self._base(of, b) for b in owner.bases]

    def implementers(self, interface: TypeRef) -> list[TypeRef] | Unknown:
        return [t for t in self.classes() if interface in self.supertypes(t)]

    # -- what the TS support asks besides -----------------------------------------------------------------------------

    def value(self, written: str, file: str) -> Typed:
        """What a value or a type the file at path `file` writes is (as `forms.py` writes it): the class of an
        instance, a class or an interface, or a module."""
        return self._value(file, written, 0) if file in self._facts else NOT_A_FILE

    def attribute(self, owner: TypeRef, name: str) -> Typed:
        """The type of a member a value of `owner` holds: a field of a class or an interface, or a module's value."""
        if not owner.name:
            file = self._files.get(owner.package)
            return self._held(self._export(file, name, 0), 0) if file is not None else NOT_A_FILE
        found = self._lookup(owner, name, "fields", NO_FIELD, 0)
        return found if isinstance(found, Unknown) else self._held(self._declared(*found), 0)

    def supertypes(self, t: TypeRef) -> list[TypeRef]:
        """The classes and interfaces of the repo `t` derives from, nearest first."""
        out: list[TypeRef] = []
        queue = [t]
        while queue and len(out) < DEPTH:
            found = self.bases(queue.pop(0))
            for b in found if not isinstance(found, Unknown) else ():
                if isinstance(b, TypeRef) and b != t and b not in out:
                    out.append(b)
                    queue.append(b)
        return out

    def extended(self, t: TypeRef) -> TypeRef | Unknown | None:
        """What `t`'s `extends` clause names first: a class's base class; None where it names none."""
        owner = self._owner(t)
        return self._base(t, owner.extends[0]) if owner is not None and owner.extends else None

    def implemented(self, t: TypeRef) -> list[TypeRef]:
        """The types of the repo a class's `implements` clause names."""
        owner = self._owner(t)
        return [b for w in owner.implements if isinstance(b := self._base(t, w), TypeRef)] if owner is not None else []

    def holds(self, t: TypeRef, name: str) -> bool:
        """Whether the class or interface `t` declares `name` as a field: a property, a parameter property, a getter."""
        owner = self._owner(t)
        return owner is not None and name in owner.fields

    def outside_base(self, t: TypeRef) -> bool:
        """Whether a base of `t`, or of one of its bases, is one the index cannot see, which may give a member."""
        for x in (t, *self.supertypes(t)):
            found = self.bases(x)
            if isinstance(found, Unknown) or any(not isinstance(b, TypeRef) for b in found):
                return True
        return False

    def classes(self) -> list[TypeRef]:
        return [TypeRef(module_of(path), name) for path, facts in self._facts.items()
                for name, m in facts.members.items() if m.kind == "class" and name in facts.owners]

    # -- names --------------------------------------------------------------------------------------------------------

    def _value(self, file: str, written: str, depth: int) -> Typed:
        if depth > DEPTH:
            return TOO_DEEP
        kind, _, name = written.rpartition(":")
        found = self._denoted(file, name, depth)
        return self._called(found, depth) if kind == "call" else self._held(found, depth) if kind == "value" \
            else self._type(found, depth)

    def _denoted(self, file: str, dotted: str, depth: int) -> Found:
        """What a name of a module, or a member of one (`m.B`), denotes."""
        first, _, rest = dotted.partition(".")
        found = self._name(file, first, depth)
        if not rest or not isinstance(found, Denoted):
            return found
        return self._export(found.file, rest, depth + 1) if found.member is None else NO_MEMBER

    def _name(self, file: str, name: str, depth: int) -> Found:
        m = self._facts[file].members.get(name)
        if m is None:
            return NO_MEMBER
        return self._imported(file, m.written, depth) if m.kind == "import" else Denoted(file, name, m)

    def _imported(self, file: str, written: str, depth: int) -> Found:
        spec, _, remote = written.rpartition(":")
        target = self._target(file, spec)
        if not isinstance(target, str):
            return target
        return Denoted(target, "", None) if remote == "*" else self._export(target, remote, depth + 1)

    def _export(self, file: str, name: str, depth: int) -> Found:
        if depth > DEPTH:
            return TOO_DEEP
        facts = self._facts[file]
        if name in facts.exports:
            return self._name(file, facts.exports[name], depth + 1)
        if name in facts.reexports:
            return self._imported(file, facts.reexports[name], depth + 1)
        for spec in facts.stars if name != "default" else ():
            target = self._target(file, spec)
            found = self._export(target, name, depth + 1) if isinstance(target, str) else target
            if isinstance(found, (Denoted, Outside)):
                return found
        return NO_MEMBER

    def _target(self, file: str, spec: str) -> str | Outside | Unknown:
        """The file of the repo, or the package, an import in the file at `file` names."""
        key = (file, spec)
        if key not in self._targets:
            found = module_target(self._ctx, self._ctx.files_by_path[file], spec)
            self._targets[key] = NO_FILE if found is None else Outside(found.name) if isinstance(found, Package) \
                else found.path if found.path in self._facts else NOT_A_FILE
        return self._targets[key]

    # -- what a name denotes, read as a type, as a call or as a value --------------------------------------------------

    def _type(self, found: Found, depth: int) -> Typed:
        if not isinstance(found, Denoted):
            return found
        m = found.member
        if m is not None and m.kind in ("class", "interface"):
            return TypeRef(module_of(found.file), found.name)
        if m is not None and m.kind == "alias":
            return self._value(found.file, m.written, depth + 1) if m.written else Unknown(m.why)
        return ENUM if m is not None and m.kind in ("enum", "namespace") else NOT_A_TYPE

    def _called(self, found: Found, depth: int) -> Typed:
        if not isinstance(found, Denoted):
            return found
        m = found.member
        if m is None or m.kind != "function":
            return NOT_CALLABLE
        return self._value(found.file, m.written, depth + 1) if m.written else Unknown(m.why)

    def _held(self, found: Found, depth: int) -> Typed:
        if not isinstance(found, Denoted):
            return found
        m = found.member
        if m is None:
            return TypeRef(module_of(found.file), "")
        if m.kind == "value":
            return self._value(found.file, m.written, depth + 1) if m.written else Unknown(m.why)
        return CLASS_ITSELF if m.kind == "class" else FUNCTION if m.kind == "function" else ENUM

    # -- classes and interfaces ---------------------------------------------------------------------------------------

    def _owner(self, t: TypeRef) -> Owner | None:
        file = self._files.get(t.package)
        return self._facts[file].owners.get(t.name) if file is not None else None

    def _lookup(self, t: TypeRef, name: str, table: str, missing: Unknown,
                depth: int) -> tuple[TypeRef, Member] | Unknown:
        """The class or interface, `t` or one of its bases, that declares the field or the method `name`."""
        owner = self._owner(t)
        if owner is None or depth > DEPTH:
            return NOT_A_TYPE if owner is None else TOO_DEEP
        m = getattr(owner, table).get(name)
        if m is not None:
            return t, m
        outside = False
        for b in self.bases(t):
            found = self._lookup(b, name, table, missing, depth + 1) if isinstance(b, TypeRef) else BASE_OUTSIDE
            if not isinstance(found, Unknown):
                return found
            outside = outside or found == BASE_OUTSIDE
        return BASE_OUTSIDE if outside else missing

    def _base(self, t: TypeRef, written: str | Unknown) -> TypeRef | Unknown:
        return written if isinstance(written, Unknown) else self.type_named(written, self._files[t.package])

    def _declared(self, t: TypeRef, m: Member) -> Denoted:
        return Denoted(self._files[t.package], "", m)


def _public(found: Typed) -> TypeRef | Unknown:
    return OUTSIDE if isinstance(found, Outside) else found
