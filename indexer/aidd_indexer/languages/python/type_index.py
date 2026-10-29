"""Python's answers to the type questions across files, from every Python file's type facts. A module and a class are
both namespaces: a name is looked up among a module's members, then its package's submodules; among a class's, then
its bases', in the order of its MRO. The MRO is read up to its first base outside the repo: that base may give the
name, so no answer goes past it. A base the index cannot see leaves only the class's own names known, and a star
import, the module's."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from ...core.types import Field, TypeIndex, TypeRef, Unknown
from .forms import UNBOUND, Member
from .modules import Modules, module_path
from .type_facts import EMPTY, Namespace, PyTypes

if TYPE_CHECKING:
    from ...core.model import FileInfo
    from ..base import ResolveContext

DEPTH = 16                          # names followed through imports and values, at most

OUTSIDE = Unknown("a type of a package outside the repo")
ATTRIBUTE_OUTSIDE = Unknown("an attribute of a type outside the repo")
NOT_A_FILE = Unknown("not a Python file of the repo")
NO_MODULE = Unknown("a relative import of no module of the repo")
UNSEEN_MODULE = Unknown("a module of the repo's names, under a root its imports are not looked for in")
NOT_A_CLASS = Unknown("a base that is not a class")
NO_MEMBER = Unknown("its module or class declares no such name")
BASE_OUTSIDE = Unknown("an attribute a base outside the repo may give")
METHOD_OUTSIDE = Unknown("a method a base outside the repo may give, ahead in the MRO")
NO_METHOD = Unknown("no class of its MRO declares the method")
NOT_A_METHOD = Unknown("its class declares the name, not as a method")
NOT_A_TYPE = Unknown("a function, not a class or a module")
NOT_CALLABLE = Unknown("a call of what is not a class or a function")
NO_MRO = Unknown("bases CPython cannot order")
SUPER = Unknown("super() in a class of several bases, or of none")
ONE_RESULT = Unknown("a Python function returns one value")
TOO_DEEP = Unknown("a chain of names longer than the index follows")


class Outside(NamedTuple):
    """A class, a module or a function of a package outside the repo, as the repo names it (`threading:Thread`)."""
    name: str


class Denoted(NamedTuple):
    """What a name denotes: a class, a module, an instance of a class, or a function and the file declaring it."""
    kind: str
    type: TypeRef | None = None
    file: FileInfo | None = None
    member: Member | None = None


def typed(types: PythonTypeIndex, file: str, written: str, path: tuple[str, ...]) -> TypeRef | Outside | Unknown:
    """The type of a receiver as the file at path `file` writes it, then of the attributes `path` names. A type outside
    the repo only where the chain ends in it: an attribute of one may hold a value of the repo."""
    found = types.value(written, file)
    for name in path:
        if isinstance(found, Outside):
            return ATTRIBUTE_OUTSIDE
        if not isinstance(found, TypeRef):
            return found
        found = types.attribute(found, name)
    return found


def qualified(t: TypeRef) -> str:
    return f"{t.package}:{t.name}" if t.name else t.package


def ref(qualified_type: str) -> TypeRef:
    package, _, name = qualified_type.partition(":")
    return TypeRef(package, name)


class PythonTypeIndex(TypeIndex):
    """A type is its module's path without `.py` (`app/models`, `app/__init__`) and its path in the module
    (`Outer.Inner`), "" for the module itself."""

    def __init__(self, ctx: ResolveContext) -> None:
        self._ctx = ctx
        self._modules = Modules(ctx)
        self._linear: dict[TypeRef, list[TypeRef | Outside] | Unknown] = {}

    def type_named(self, written: str, file: str) -> TypeRef | Unknown:
        return _public(self.value(written, file))

    def return_type(self, function: str, file: str, result: int = 0) -> TypeRef | Unknown:
        return _public(self.value(f"call:{function}", file)) if result == 0 else ONE_RESULT

    def method_return_type(self, owner: TypeRef, method: str, result: int = 0) -> TypeRef | Unknown:
        return _public(self._call(self._attribute(_held(owner), method, 0), 0)) if result == 0 else ONE_RESULT

    def field(self, owner: TypeRef, name: str) -> Field | Unknown:
        found = self.attribute(owner, name)
        if isinstance(found, Unknown):
            return found
        where = self._lookup(owner, name) if owner.name else None
        declared = None if where is None or isinstance(where, Unknown) else where
        return Field(_public(found), declared[1].written if declared else "", bool(declared) and declared[0] != owner)

    def method(self, owner: TypeRef, name: str) -> TypeRef | Unknown:
        found = self._lookup(owner, name, METHOD_OUTSIDE, NO_METHOD)
        if isinstance(found, Unknown):
            return found
        return found[0] if found[1].kind == "function" else NOT_A_METHOD

    def bases(self, of: TypeRef) -> list[TypeRef | Unknown] | Unknown:
        return [b if isinstance(b, (TypeRef, Unknown)) else OUTSIDE for b in self._bases(of)]

    def value(self, written: str, file: str) -> TypeRef | Outside | Unknown:
        """What a value the file at path `file` writes is (as `forms.py` writes it): the class of an instance, a class
        or a module."""
        f = self._ctx.files_by_path.get(file)
        return self._value(f, written, 0) if f is not None else NOT_A_FILE

    def attribute(self, owner: TypeRef, name: str) -> TypeRef | Outside | Unknown:
        return self._type(self._attribute(_held(owner), name, 0))

    def supertypes(self, cls: TypeRef) -> list[TypeRef]:
        """The repo's classes after `cls` in its MRO, up to the first base outside the repo."""
        found = self._mro(cls) if cls.name else []
        out: list[TypeRef] = []
        for t in found[1:] if not isinstance(found, Unknown) else ():
            if isinstance(t, Outside):
                break
            out.append(t)
        return out

    def mro(self, cls: TypeRef) -> list[TypeRef | Outside] | Unknown:
        return self._mro(cls)

    def outside_base(self, cls: TypeRef) -> bool:
        found = self._mro(cls) if cls.name else []
        return not isinstance(found, Unknown) and any(isinstance(t, Outside) for t in found)

    def _value(self, f: FileInfo, written: str, depth: int) -> TypeRef | Outside | Unknown:
        if written.startswith("call:"):
            return self._call(self._name(f, written[5:], depth), depth)
        if written.startswith("super:"):
            return self._super(self._name(f, written[6:], depth))
        return self._type(self._name(f, written, depth))

    def _type(self, found: Denoted | Outside | Unknown) -> TypeRef | Outside | Unknown:
        if isinstance(found, Denoted):
            return found.type if found.kind != "function" else NOT_A_TYPE
        return found

    def _call(self, found: Denoted | Outside | Unknown, depth: int) -> TypeRef | Outside | Unknown:
        """What a call returns: an instance of a class, or what a function declares it returns. What a package's class
        or function returns is the package's."""
        if not isinstance(found, Denoted):
            return found
        if found.kind == "class":
            return found.type
        if found.kind != "function":
            return NOT_CALLABLE
        member = found.member
        return self._value(found.file, member.written, depth + 1) if member.written else Unknown(member.why)

    def _super(self, found: Denoted | Outside | Unknown) -> TypeRef | Outside | Unknown:
        """What follows a class in its MRO, read where it is its only base: then the base's own MRO is the rest."""
        if not isinstance(found, Denoted) or found.kind != "class":
            return found if isinstance(found, Unknown) else SUPER
        bases = self._bases(found.type)
        return bases[0] if len(bases) == 1 else SUPER

    def _name(self, f: FileInfo, dotted: str, depth: int) -> Denoted | Outside | Unknown:
        first, *rest = dotted.split(".")
        found = self._module_member(TypeRef(module_path(f), ""), first, depth)
        for name in rest:
            found = self._attribute(found, name, depth)
        return found

    def _attribute(self, found: Denoted | Outside | Unknown, name: str, depth: int) -> Denoted | Outside | Unknown:
        if isinstance(found, Outside):
            return Outside(f"{found.name}.{name}")
        if not isinstance(found, Denoted):
            return found
        if depth > DEPTH:
            return TOO_DEEP
        if found.kind == "module":
            return self._module_member(found.type, name, depth + 1)
        if found.kind == "function":
            return NOT_A_TYPE
        where = self._lookup(found.type, name)
        return where if isinstance(where, Unknown) else self._denote(self._file_of(where[0]), where[1], depth + 1)

    def _module_member(self, module: TypeRef, name: str, depth: int) -> Denoted | Outside | Unknown:
        """A module's member, or else its package's submodule: `from p import x` reads them in that order."""
        f = self._file_of(module)
        member = self._namespace(module).members.get(name)
        if member is not None and f is not None:
            return self._denote(f, member, depth)
        sub = self._modules.submodule(module.package, name)
        if sub is not None:
            return Denoted("module", TypeRef(sub, ""))
        mro = self._mro(module)
        return mro if isinstance(mro, Unknown) else NO_MEMBER

    def _denote(self, f: FileInfo, member: Member, depth: int) -> Denoted | Outside | Unknown:
        if depth > DEPTH:
            return TOO_DEEP
        if member.kind == "class":
            return Denoted("class", TypeRef(module_path(f), member.written))
        if member.kind == "function":
            return Denoted("function", None, f, member)
        if member.kind == "value":
            found = self._value(f, member.written, depth + 1)
            return _held(found) if isinstance(found, TypeRef) else found
        if member.kind in ("module", "import"):
            return self._imported(f, member.written, depth + 1)
        return Unknown(member.why)

    def _imported(self, f: FileInfo, written: str, depth: int) -> Denoted | Outside | Unknown:
        """`import m`'s module, or `from m import x`'s `x` (`m:x`)."""
        spec, colon, name = written.partition(":")
        module = self._import(f, spec)
        if isinstance(module, Outside):
            return Outside(written)
        if isinstance(module, Unknown):
            return module
        return self._module_member(module, name, depth) if colon else Denoted("module", module)

    def _import(self, f: FileInfo, spec: str) -> TypeRef | Outside | Unknown:
        found = self._modules.imported(f, spec)
        if found is not None:
            return TypeRef(found, "")
        return NO_MODULE if spec.startswith(".") else UNSEEN_MODULE if self._modules.holds(spec) else Outside(spec)

    def _lookup(self, cls: TypeRef, name: str, outside: Unknown = BASE_OUTSIDE,
                missing: Unknown = NO_MEMBER) -> tuple[TypeRef, Member] | Unknown:
        """The class of `cls`'s MRO that declares `name`, and what it is."""
        mro = self._mro(cls)
        for t in mro if not isinstance(mro, Unknown) else [cls]:
            if isinstance(t, Outside):
                return outside
            member = self._namespace(t).members.get(name)
            if member is not None:
                return t, member
        return mro if isinstance(mro, Unknown) else missing

    def _mro(self, cls: TypeRef) -> list[TypeRef | Outside] | Unknown:
        if cls not in self._linear:
            self._linear[cls] = NO_MRO              # a class among its own bases has none
            self._linear[cls] = self._c3(cls)
        return self._linear[cls]

    def _c3(self, cls: TypeRef) -> list[TypeRef | Outside] | Unknown:
        bases = self._bases(cls)
        heads: list[list[TypeRef | Outside]] = []
        for base in bases:
            found = self._mro(base) if isinstance(base, TypeRef) else base if isinstance(base, Unknown) else [base]
            if isinstance(found, Unknown):
                return found
            heads.append(found)
        merged = _merge(heads + [list(bases)])
        return [cls, *merged] if merged is not None else NO_MRO

    def _bases(self, cls: TypeRef) -> list[TypeRef | Outside | Unknown]:
        """A class's bases: a builtin is outside the repo; one the index cannot see, as a star import's, is unknown."""
        f = self._file_of(cls)
        out: list[TypeRef | Outside | Unknown] = []
        for i, written in enumerate(self._namespace(cls).bases):
            found = written if isinstance(written, Unknown) else self._name(f, written, 0) if f is not None else NOT_A_FILE
            if isinstance(found, Denoted):
                out.append(found.type if found.kind == "class" else NOT_A_CLASS)
            else:
                out.append(Outside(f"{qualified(cls)}#{i}") if found == UNBOUND else found)
        return out

    def _namespace(self, t: TypeRef) -> Namespace:
        f = self._file_of(t)
        return PyTypes.of(self._ctx.facts.get(f.id)).namespaces.get(t.name, EMPTY) if f is not None else EMPTY

    def _file_of(self, t: TypeRef) -> FileInfo | None:
        return self._ctx.files_by_path.get(f"{t.package}.py")


def _held(t: TypeRef) -> Denoted:
    """A value of the type `t`: a module, or an instance of a class."""
    return Denoted("module" if not t.name else "instance", t)


def _public(found: TypeRef | Outside | Unknown) -> TypeRef | Unknown:
    return OUTSIDE if isinstance(found, Outside) else found


def _merge(sequences: list[list]) -> list | None:
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
