"""C#'s answers to the type service. A type of the repo is found by its simple name from a file: the only one of that
name, or the one C# finds first from the file (its namespace, the ones around it, then its `using`s and its project's
`global using`s). Then its members, typed with what its type parameters are given, its bases and the types that
implement an interface. Built once per repo, on its first question, from every C# file's type facts: every receiver,
base and implementer asks, and a scan of all files per question is quadratic in the repo."""

from __future__ import annotations

import re
from typing import Iterator, NamedTuple

from ...core.model import FileInfo
from ...core.types import Field, TypeIndex, TypeRef, Unknown
from ..base import ResolveContext
from .type_facts import CsType, CsTypes, scopes
from .type_syntax import bare, type_arguments

NOT_A_FILE = Unknown("not a file of the repo")
OUTSIDE = Unknown("no type of the repo has that name, or the file sees more than one")
UNDECLARED = Unknown("no file of the repo declares it")
NO_FIELD = Unknown("neither the type nor a base it names declares that member")
NO_METHOD = Unknown("neither the type nor its bases declare the method")
NOT_A_NAME = Unknown("the method declares no result that is a name, or its overloads declare two")
INTERFACE = re.compile(r"^I[A-Z]")
Arg = tuple[TypeRef | Unknown, str]                         # what a type parameter is: a type, as the code writes it


class Declared(NamedTuple):
    """A type of the repo, as one file declares it."""
    qualified: str
    type: CsType
    file: FileInfo


def qualified(t: TypeRef) -> str:
    return f"{t.package}.{t.name}" if t.package else t.name


def ref(q: str) -> TypeRef:
    package, _, name = q.rpartition(".")
    return TypeRef(package, name)


class CsTypeIndex(TypeIndex):
    """A type is its namespace ("" for none) and its simple name."""

    def __init__(self, ctx: ResolveContext) -> None:
        self._ctx = ctx
        self._by_name: dict[str, list[Declared]] | None = None
        self._types: dict[str, list[Declared]] = {}
        self._implementers: dict[str, list[str]] | None = None
        self._project_usings: dict[str, frozenset[str]] | None = None
        self._bindings: dict[str, dict[str, dict[str, Arg]]] = {}
        self.chains: dict[str, list[str]] | None = None     # what the DI container builds (`wiring`), on first ask

    # ---- the type service's questions
    def type_named(self, written: str, file: str) -> TypeRef | Unknown:
        f = self.file(file)
        if f is None:
            return NOT_A_FILE
        found = self.lookup(f, written)
        return ref(found.qualified) if found is not None else OUTSIDE

    def field(self, owner: TypeRef, name: str, args: tuple[Arg, ...] = ()) -> Field | Unknown:
        """Declared on the type, else on the first base it names that declares it (one level up). Its type is read in
        the file that declares the member; a type parameter's is what `bindings` give it, `args` given to `owner`."""
        parts = self.parts(qualified(owner), last=True)
        member = self._member(parts, name)
        if member is None:
            return NO_FIELD if parts else UNDECLARED
        return self._typed(member[0], name, self.bindings(qualified(owner), args), member[1])

    def bases(self, of: TypeRef) -> list[TypeRef | Unknown] | Unknown:
        """The bases every declaration of the type names (a partial type has several); one the file that names it
        cannot find in the repo is Unknown."""
        q = qualified(of)
        found = [d for d in self.named(of.name) if d.qualified == q]
        if not found:
            return UNDECLARED
        return [ref(b.qualified) if b is not None else OUTSIDE
                for d in found for b in (self.lookup(d.file, n) for n in d.type.bases)]

    def implementers(self, interface: TypeRef) -> list[TypeRef] | Unknown:
        """Every class, record or struct of the repo that names a base of the interface's simple name."""
        if self._implementers is None:
            self._implementers = {}
            for d in self.declarations():
                for b in d.type.bases if d.type.kind != "interface" else ():
                    self._implementers.setdefault(b, []).append(d.qualified)
        return [ref(q) for q in sorted(set(self._implementers.get(interface.name, [])))]

    def method_return_type(self, owner: TypeRef, method: str, result: int = 0) -> TypeRef | Unknown:
        return self.method_result(owner, method, False) if result == 0 else NOT_A_NAME

    # ---- C#'s own
    def method_result(self, owner: TypeRef, method: str, awaited: bool) -> TypeRef | Unknown:
        return self.result_of(owner, method, awaited)[0]

    def result_of(self, owner: TypeRef, method: str, awaited: bool,
                  args: tuple[Arg, ...] = ()) -> tuple[TypeRef | Unknown, tuple[Arg, ...]]:
        """What `owner`'s method returns (`awaited`: what awaiting it gives), declared on the type, any of its parts,
        or the shallowest base that declares it, read in the file that declares it, and the type arguments it passes; a
        type parameter's, what `bindings` give it, `args` given to `owner`."""
        seen, queue = {qualified(owner)}, [qualified(owner)]
        while queue:
            q = queue.pop(0)
            found = next(((d, d.type.results[method]) for d in self.parts(q, last=True) if method in d.type.results),
                         None)
            if found is not None:
                env = self.bindings(qualified(owner), args).get(found[0].qualified, {})
                return self._result(found[0], found[1][1] if awaited else found[1][0], env)
            bases = self.bases(ref(q))
            for b in bases if not isinstance(bases, Unknown) else ():
                if not isinstance(b, Unknown) and qualified(b) not in seen:
                    seen.add(qualified(b))
                    queue.append(qualified(b))
        return NO_METHOD, ()

    def ancestry(self, q: str) -> tuple[list[str], set[str]]:
        """The type and its bases in the repo, nearest first, and the names its chain gives to bases outside the
        repo."""
        chain, outside = [q], set()
        for t in chain:                                     # breadth first: the list grows as it is read
            for d in (d for d in self.named(t.rpartition(".")[2]) if d.qualified == t):
                for b in d.type.bases:
                    found = self.lookup(d.file, b)
                    if found is None:
                        outside.add(b)
                    elif found.qualified not in chain:
                        chain.append(found.qualified)
        return chain, outside

    def file(self, path: str) -> FileInfo | None:
        return self._ctx.files_by_path.get(path)

    def files(self) -> Iterator[tuple[FileInfo, CsTypes]]:
        """Every C# file of the repo with its type facts, in file order."""
        for fid, facts in self._ctx.facts.items():
            f = self._ctx.files_by_id.get(fid)
            if f is not None and f.language == "csharp":
                yield f, CsTypes.of(facts)

    def declarations(self) -> Iterator[Declared]:
        """Every type the repo's C# files declare, in file order."""
        for f, facts in self.files():
            for name, t in facts.types.items():
                yield Declared(".".join(p for p in (t.ns, t.outer, name) if p), t, f)

    def named(self, simple: str) -> list[Declared]:
        if self._by_name is None:
            self._by_name = {}
            for d in self.declarations():
                self._by_name.setdefault(d.qualified.rpartition(".")[2], []).append(d)
        return self._by_name.get(simple, [])

    def is_type_name(self, name: str) -> bool:
        """A simple name a type of the repo has, or the qualified name of one."""
        return any(d.qualified == name for d in self.named(name.rpartition(".")[2])) if "." in name \
            else bool(self.named(name))

    def parts(self, q: str, last: bool) -> list[Declared]:
        """Every part of a partial type. Two declarations of a type that is not partial are two types of one name,
        and a question reads one of them, as it always has: the last, or the first."""
        found = [d for d in self.named(q.rpartition(".")[2]) if d.qualified == q]
        if len(found) > 1 and all(d.type.partial for d in found):
            return found
        return found[-1:] if last else found[:1]

    def lookup(self, file: FileInfo, simple: str, arity: int | None = None) -> Declared | None:
        """The type a file means by a simple name: the only one of that name; one nested in a type the file declares;
        or the first C# finds from the file (its namespace, the ones around it, then the `using`s, its project's
        `global using`s among them), when no other is found at that step. Of the global namespace, only the file's
        project counts: other projects keep their programs there. A partial type counts once, by its first part.
        Given the `arity` the name is written with, only a type of that many type parameters the file sees counts, as
        C# binds it: the only one of the name may be a framework's (`ISet<T>`) the repo's homonym does not stand for."""
        if "." in simple:                                   # the enclosing type, by its qualified name
            found = [d for d in self._types_named(simple.rpartition(".")[2]) if d.qualified == simple]
            return found[0] if len(found) == 1 else None
        hits = self._types_named(simple)
        if arity is not None:
            hits = [h for h in hits if len(h.type.params) == arity]
        elif len(hits) <= 1:
            return hits[0] if hits else None
        inner = [h for h in hits if h.type.outer and h.file.id == file.id]
        if inner:
            return inner[0] if len(inner) == 1 else None
        for scope in scopes(CsTypes.of(self._ctx.facts.get(file.id)), self.project_usings(file)):
            seen = [h for h in hits if h.type.ns in scope and not h.type.outer
                    and (h.type.ns is not None or h.file.module_id == file.module_id)]
            if seen:
                return seen[0] if len(seen) == 1 else None
        return None

    def project_usings(self, file: FileInfo) -> frozenset[str]:
        """What the `global using`s of the file's project import: every file of the project sees it."""
        if self._project_usings is None:
            found: dict[str, set[str]] = {}
            for f, facts in self.files():
                found.setdefault(f.module_id, set()).update(facts.global_usings)
            self._project_usings = {m: frozenset(u) for m, u in found.items()}
        return self._project_usings.get(file.module_id, frozenset())

    def member(self, owner: str, name: str) -> Field | None:
        """The member `name` the type `owner` (qualified) declares in any part, or a class of the repo it derives from,
        the nearest first; its type is read in the file that declares it, a type parameter's as `bindings` give it."""
        for t in self.ancestry(owner)[0]:
            for d in self.parts(t, last=True):
                if name in d.type.members and (t == owner or d.type.kind != "interface"):
                    return self._typed(d, name, self.bindings(owner), t != owner)
        return None

    def bindings(self, owner: str, args: tuple[Arg, ...] = ()) -> dict[str, dict[str, Arg]]:
        """What each type parameter of the type `owner` (qualified), and of each base of the repo it derives from, is:
        the type arguments `args` given to `owner`, else what its one constraint names; a base's, what the base list of
        the type deriving from it passes, read in the file that writes it."""
        if not args and owner in self._bindings:
            return self._bindings[owner]
        out: dict[str, dict[str, Arg]] = {}
        queue = [(owner, args)]
        for q, given in queue:                              # breadth first: the list grows as it is read
            parts = self.parts(q, last=True) if q not in out else []
            if parts:
                out[q] = env = {p: given[i] if i < len(given) else self.read(parts[0].file, bound)
                                for i, (p, bound) in enumerate(parts[0].type.params)}
                queue += [(b.qualified, self._passed(d, name, env)) for d in parts for name in d.type.bases
                          if (b := self.lookup(d.file, name)) is not None]
        if not args:
            self._bindings[owner] = out
        return out

    def read(self, file: FileInfo | None, written: str) -> Arg:
        """A type written in `file`, with the type of the repo it names there."""
        found = self.lookup(file, written) if file is not None and written else None
        return (ref(found.qualified) if found is not None else OUTSIDE), written

    def nested(self, owner: str, name: str) -> str | None:
        """The type `name` nested in the type `owner` (qualified) or in one it derives from, the nearest first."""
        found = {d.qualified for d in self.named(name)}
        return next((f"{t}.{name}" for t in self.ancestry(owner)[0] if f"{t}.{name}" in found), None)

    def class_base_outside(self, owner: str) -> bool:
        """The type `owner` (qualified) derives from a class outside the repo, which may declare any member."""
        return any(not INTERFACE.match(b) for b in self.ancestry(owner)[1])

    def explicit_interface(self, implementation: str, method: str) -> str | None:
        """The interface `implementation` implements `method` for explicitly, if it does."""
        return next((d.type.explicit[method] for d in self.parts(implementation, last=False)
                     if method in d.type.explicit), None)

    def _types_named(self, simple: str) -> list[Declared]:
        if simple not in self._types:
            hits = self.named(simple)
            partial = {d.qualified for d in hits if d.type.partial} - {d.qualified for d in hits if not d.type.partial}
            firsts = {q: next(d for d in hits if d.qualified == q) for q in partial}
            self._types[simple] = [d for d in hits if d.qualified not in partial or firsts[d.qualified] is d]
        return self._types[simple]

    def _member(self, parts: list[Declared], name: str) -> tuple[Declared, bool] | None:
        """The declaration of the member `name`: on the type, else on the first base it names (promoted)."""
        for d in parts:
            if name in d.type.members:
                return d, False
        for d in parts:
            for b in d.type.bases:
                bt = self.lookup(d.file, b)
                found = next((p for p in self.parts(bt.qualified, last=True) if name in p.type.members), None) \
                    if bt is not None else None
                if found is not None:
                    return found, True
        return None

    def _typed(self, d: Declared, name: str, bindings: dict[str, dict[str, Arg]], promoted: bool) -> Field:
        """`d`'s member `name`, with its type: a type parameter's, what `bindings` give it."""
        written = d.type.members[name]
        typ, written = bindings.get(d.qualified, {}).get(written) or self.read(d.file, written)
        return Field(typ, written, promoted)

    def _result(self, d: Declared, written: str, env: dict[str, Arg]) -> tuple[TypeRef | Unknown, tuple[Arg, ...]]:
        """The type `d`'s method writes as its result, and the type arguments it passes: one of `d`'s type parameters,
        what `env` gives it."""
        if not written:
            return NOT_A_NAME, ()
        typ = (env.get(bare(written)) or self.read(d.file, bare(written)))[0]
        return typ, tuple(env.get(a) or self.read(d.file, a) for a in type_arguments(written))

    def _passed(self, d: Declared, base: str, env: dict[str, Arg]) -> tuple[Arg, ...]:
        """The type arguments `d`'s base list passes its base `base`: one of `d`'s type parameters, what it is."""
        return tuple(env.get(a) or self.read(d.file, a) for a in dict(d.type.generic_bases).get(base, ()))
