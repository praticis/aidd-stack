"""C#'s answers to the type service. A type of the repo is found by its simple name from a file: the only one of that
name, or the only one among the namespaces the file can see (its own and its `using`s). Then its members, its bases,
the types that implement an interface, and what the DI container builds for one. Built once per repo, on its first
question, from every C# file's type facts: every receiver, base and implementer asks, and a scan of all files per
question is quadratic in the repo."""

from __future__ import annotations

import re
from typing import Iterator, NamedTuple

from ...core.config import is_test_path
from ...core.model import FileInfo
from ...core.types import Field, TypeIndex, TypeRef, Unknown
from ..base import ResolveContext
from .type_facts import CsType, CsTypes

NOT_A_FILE = Unknown("not a file of the repo")
OUTSIDE = Unknown("no type of the repo has that name, or the file sees more than one")
UNDECLARED = Unknown("no file of the repo declares it")
NO_FIELD = Unknown("neither the type nor a base it names declares that member")
DEPTH = 4                                   # bases followed for a member a caller's own type inherits
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


class CsTypeIndex(TypeIndex):
    """A type is its namespace ("" for none) and its simple name."""

    def __init__(self, ctx: ResolveContext) -> None:
        self._ctx = ctx
        self._by_name: dict[str, list[Declared]] | None = None
        self._by_q: dict[str, Declared] | None = None
        self._implementers: dict[str, list[str]] | None = None
        self._chains: dict[str, list[str]] | None = None

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
        found = self.last(qualified(owner))
        member = self._member(found, name) if found is not None else None
        if member is None:
            return NO_FIELD if found is not None else UNDECLARED
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

    # ---- C#'s own
    def declarations(self) -> Iterator[Declared]:
        """Every type the repo's C# files declare, in file order."""
        for fid, facts in self._ctx.facts.items():
            f = self._ctx.files_by_id.get(fid)
            if f is not None and f.language == "csharp":
                for name, t in CsTypes.of(facts).types.items():
                    yield Declared((t.ns + "." if t.ns else "") + name, t, f)

    def named(self, simple: str) -> list[Declared]:
        if self._by_name is None:
            self._by_name = {}
            for d in self.declarations():
                self._by_name.setdefault(d.qualified.rpartition(".")[2], []).append(d)
        return self._by_name.get(simple, [])

    def is_type_name(self, simple: str) -> bool:
        return bool(self.named(simple))

    def last(self, q: str) -> Declared | None:
        """The last declaration of a qualified type: the only one, unless the type is partial."""
        if self._by_q is None:
            self._by_q = {d.qualified: d for d in self.declarations()}
        return self._by_q.get(q)

    def lookup(self, file: FileInfo, simple: str) -> Declared | None:
        """The type a file means by a simple name, preferring the namespaces it can see (its own, its usings)."""
        hits = self.named(simple)
        if len(hits) <= 1:
            return hits[0] if hits else None
        mine = CsTypes.of(self._ctx.facts.get(file.id))
        visible = set(mine.usings) | ({mine.file_ns} if mine.file_ns else set())
        seen = [h for h in hits if h.type.ns in visible]
        return seen[0] if len(seen) == 1 else None

    def inherited_member_type(self, owner: str, member: str) -> str | None:
        """Declared type of `member` on the type `owner` (qualified) or on its bases in this repo, a few levels up;
        "" when a base outside the repo may declare it; None when no type of the chain has it."""
        found = self.last(owner)
        for _ in range(DEPTH):
            if found is None:
                return None
            if member in found.type.members:
                return found.type.members[member]
            base = next((bt for b in found.type.bases if (bt := self.lookup(found.file, b)) is not None), None)
            if base is None and any(not INTERFACE.match(b) for b in found.type.bases):
                return ""                                   # a class base outside the repo
            found = base
        return None

    def explicit_interface(self, implementation: str, method: str) -> str | None:
        """The interface the first declaration of `implementation` implements `method` for explicitly, if it does."""
        found = next((d for d in self.named(implementation.rpartition(".")[2]) if d.qualified == implementation), None)
        return found.type.explicit.get(method) if found is not None else None

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

    def _member(self, found: Declared, name: str) -> tuple[str, FileInfo, bool] | None:
        written = found.type.members.get(name)
        if written is not None:
            return written, found.file, False
        for b in found.type.bases:
            bt = self.lookup(found.file, b)
            if bt is not None and name in bt.type.members:
                return bt.type.members[name], bt.file, True
        return None
