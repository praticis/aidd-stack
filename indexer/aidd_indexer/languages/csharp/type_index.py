"""C#'s answers to the type service. A type of the repo is found by its simple name from a file: the only one of that
name, or the one C# finds first from the file (its namespace, the ones around it, then its `using`s and its project's
`global using`s). Then its members, its bases, the types that implement an interface, and what the DI container builds
for one. Built once per repo, on its first question, from every C# file's type facts: every receiver, base and
implementer asks, and a scan of all files per question is quadratic in the repo."""

from __future__ import annotations

import re
from typing import Iterator, NamedTuple

from ...core.config import is_test_path
from ...core.model import FileInfo
from ...core.types import Field, TypeIndex, TypeRef, Unknown
from ..base import ResolveContext
from .type_facts import CsType, CsTypes, scopes

NOT_A_FILE = Unknown("not a file of the repo")
OUTSIDE = Unknown("no type of the repo has that name, or the file sees more than one")
UNDECLARED = Unknown("no file of the repo declares it")
NO_FIELD = Unknown("neither the type nor a base it names declares that member")
NO_METHOD = Unknown("neither the type nor its bases declare the method")
NOT_A_NAME = Unknown("the method declares no result that is a name, or its overloads declare two")
INTERFACE = re.compile(r"^I[A-Z]")


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


def typed(t: CsType, written: str) -> str:
    """A type `t`'s member writes `written` for its type: one of `t`'s type parameters is the one type its constraints
    name, "" for none."""
    return dict(t.params).get(written, written)


class CsTypeIndex(TypeIndex):
    """A type is its namespace ("" for none) and its simple name."""

    def __init__(self, ctx: ResolveContext) -> None:
        self._ctx = ctx
        self._by_name: dict[str, list[Declared]] | None = None
        self._types: dict[str, list[Declared]] = {}
        self._implementers: dict[str, list[str]] | None = None
        self._chains: dict[str, list[str]] | None = None
        self._project_usings: dict[str, frozenset[str]] | None = None

    # ---- the type service's questions
    def type_named(self, written: str, file: str) -> TypeRef | Unknown:
        f = self._ctx.files_by_path.get(file)
        if f is None:
            return NOT_A_FILE
        found = self.lookup(f, written)
        return ref(found.qualified) if found is not None else OUTSIDE

    def field(self, owner: TypeRef, name: str) -> Field | Unknown:
        """Declared on the type, else on the first base it names that declares it (one level up). Its type is read in
        the file that declares the member."""
        parts = self.parts(qualified(owner), last=True)
        member = self._member(parts, name)
        if member is None:
            return NO_FIELD if parts else UNDECLARED
        written, file, promoted = member
        typ = self.lookup(file, written)
        return Field(ref(typ.qualified) if typ is not None else OUTSIDE, written, promoted)

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
        """What `owner`'s method returns (`awaited`: what awaiting it gives), declared on the type, any of its parts,
        or the shallowest base that declares it, and read in the file that declares it."""
        seen, queue = {qualified(owner)}, [qualified(owner)]
        while queue:
            q = queue.pop(0)
            found = next(((d, d.type.results[method]) for d in self.parts(q, last=True) if method in d.type.results),
                         None)
            if found is not None:
                written = found[1][1] if awaited else found[1][0]
                typ = self.lookup(found[0].file, written) if written else None
                return ref(typ.qualified) if typ is not None else OUTSIDE if written else NOT_A_NAME
            bases = self.bases(ref(q))
            for b in bases if not isinstance(bases, Unknown) else ():
                if not isinstance(b, Unknown) and qualified(b) not in seen:
                    seen.add(qualified(b))
                    queue.append(qualified(b))
        return NO_METHOD

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

    def declarations(self) -> Iterator[Declared]:
        """Every type the repo's C# files declare, in file order."""
        for fid, facts in self._ctx.facts.items():
            f = self._ctx.files_by_id.get(fid)
            if f is not None and f.language == "csharp":
                for name, t in CsTypes.of(facts).types.items():
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

    def lookup(self, file: FileInfo, simple: str) -> Declared | None:
        """The type a file means by a simple name: the only one of that name; one nested in a type the file declares;
        or the first C# finds from the file (its namespace, the ones around it, then the `using`s, its project's
        `global using`s among them), when no other is found at that step. Of the global namespace, only the file's
        project counts: other projects keep their programs there. A partial type counts once, by its first part."""
        if "." in simple:                                   # the enclosing type, by its qualified name
            found = [d for d in self._types_named(simple.rpartition(".")[2]) if d.qualified == simple]
            return found[0] if len(found) == 1 else None
        hits = self._types_named(simple)
        if len(hits) <= 1:
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
            for fid, facts in self._ctx.facts.items():
                f = self._ctx.files_by_id.get(fid)
                if f is not None and CsTypes.of(facts).global_usings:
                    found.setdefault(f.module_id, set()).update(CsTypes.of(facts).global_usings)
            self._project_usings = {m: frozenset(u) for m, u in found.items()}
        return self._project_usings.get(file.module_id, frozenset())

    def member(self, owner: str, name: str) -> Field | None:
        """The member `name` the type `owner` (qualified) declares in any part, or a class of the repo it derives from,
        the nearest first; its type is read in the file that declares it."""
        for t in self.ancestry(owner)[0]:
            for d in self.parts(t, last=True):
                if name in d.type.members and (t == owner or d.type.kind != "interface"):
                    written = typed(d.type, d.type.members[name])
                    typ = self.lookup(d.file, written)
                    return Field(ref(typ.qualified) if typ is not None else OUTSIDE, written, t != owner)
        return None

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

    def handlers(self, file: FileInfo, message_type: str, handler_bases: frozenset[str]) -> list[str]:
        """The types whose generic base among `handler_bases` takes the message type sent from `file` first."""
        sent = self.lookup(file, message_type)
        out: list[str] = []
        for d in self.declarations():
            for base, targs in d.type.generic_bases if d.type.kind != "interface" else ():
                if base in handler_bases and targs and self._same(sent, d.file, targs[0], message_type):
                    out.append(d.qualified)
        return sorted(set(out))

    def di_chain(self, interface: str) -> list[str] | None:
        """What the container builds for an interface (qualified), innermost first: `[UpdateCacheStep,
        CommitActivityStep, CheckTodoStep]` for `AddScoped<I, UpdateCacheStep>(); Decorate<I, CommitActivityStep>();
        Decorate<I, CheckTodoStep>()`. An interface registered in more than one file (environments, tests) has none:
        which one runs cannot be told."""
        if self._chains is None:
            found: dict[str, list[list[str]]] = {}
            for fid, facts in self._ctx.facts.items():
                f = self._ctx.files_by_id.get(fid)
                if f is not None and f.language == "csharp" and not is_test_path(f.path):
                    for qi, chain in self._registered(f, CsTypes.of(facts)).items():
                        found.setdefault(qi, []).append(chain)
            self._chains = {qi: chains[0] for qi, chains in found.items() if len(chains) == 1 and "" not in chains[0]}
        return self._chains.get(interface)

    def _registered(self, f: FileInfo, facts: CsTypes) -> dict[str, list[str]]:
        here: dict[str, list[str]] = {}
        for method, (iface, impl) in facts.registrations:
            qi, qt = self.lookup(f, iface), self.lookup(f, impl)
            if qi is None or qt is None:
                continue
            if method == "Decorate":
                if qi.qualified in here:
                    here[qi.qualified].append(qt.qualified)
            elif qi.qualified in here and len(here[qi.qualified]) == 1:
                here[qi.qualified] = [""]                   # registered twice for one interface: no single base
            else:
                here[qi.qualified] = [qt.qualified]
        return here

    def _same(self, sent: Declared | None, file: FileInfo, handled_name: str, message_type: str) -> bool:
        """Both in the repo: the same qualified type; both outside (a package's message): the same name."""
        handled = self.lookup(file, handled_name)
        if sent and handled:
            return sent.qualified == handled.qualified
        return not sent and not handled and handled_name == message_type

    def _types_named(self, simple: str) -> list[Declared]:
        if simple not in self._types:
            hits = self.named(simple)
            partial = {d.qualified for d in hits if d.type.partial} - {d.qualified for d in hits if not d.type.partial}
            firsts = {q: next(d for d in hits if d.qualified == q) for q in partial}
            self._types[simple] = [d for d in hits if d.qualified not in partial or firsts[d.qualified] is d]
        return self._types[simple]

    def _member(self, parts: list[Declared], name: str) -> tuple[str, FileInfo, bool] | None:
        for d in parts:
            if name in d.type.members:
                return typed(d.type, d.type.members[name]), d.file, False
        for d in parts:
            for b in d.type.bases:
                bt = self.lookup(d.file, b)
                found = next((p for p in self.parts(bt.qualified, last=True) if name in p.type.members), None) \
                    if bt is not None else None
                if found is not None:
                    return typed(found.type, found.type.members[name]), found.file, True
        return None
