"""Go's answers to the type questions across files, from every Go file's type facts. The files of each package
directory and the methods production code declares on each type are indexed once per repo, on first use: every typed
receiver of every call asks, and a scan per question is quadratic in the repo."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from ...core.config import is_test_path
from ...core.types import Field, TypeIndex, TypeRef, Unknown
from .type_facts import GoTypes

if TYPE_CHECKING:
    from ...core.model import FileInfo, ModuleInfo
    from ..base import ResolveContext

DEPTH = 4                           # embedded types followed, at most this deep

OUTSIDE = Unknown("a type of a package outside the repo, or under no import of the file")
UNDECLARED = Unknown("no file of its package declares it")
NOT_A_FILE = Unknown("not a Go file of the repo")
NOT_A_NAME = Unknown("its declared type is not a name")
NO_FIELD = Unknown("its struct, and the structs it embeds, have no such field with a type of the repo")
TOO_DEEP = Unknown("embedded deeper than the index follows")
NO_METHODS = Unknown("not an interface of the repo whose methods are all known")
NOT_REQUIRED = Unknown("the interface does not require it")


def go_module_path(root: Path, module: ModuleInfo) -> str | None:
    gm = root / module.path / "go.mod" if module.path else root / "go.mod"
    if not gm.exists():
        return None
    for line in gm.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("module "):
            return line.split(None, 1)[1].strip()
    return None


def module_paths(ctx: ResolveContext) -> list[tuple[str, ModuleInfo]]:
    """The repo's Go modules under the path each `go.mod` declares, longest first."""
    return sorted(((mp, m) for m in ctx.modules_by_path.values()
                   if m.kind == "go-module" and (mp := go_module_path(ctx.root, m))), key=lambda t: -len(t[0]))


class GoTypeIndex(TypeIndex):
    """A type is its package's dotted directory ("" for the repo root) and its name. A type declared in several files
    of a package (under build tags) is read in the first that declares it."""

    def __init__(self, ctx: ResolveContext) -> None:
        self._ctx = ctx
        self._modules = module_paths(ctx)
        self._by_dir: dict[str, list[FileInfo]] | None = None
        self._sets: dict[TypeRef, set[str]] | None = None
        self._required: dict[TypeRef, dict[str, TypeRef] | None] = {}
        self._implementers: dict[TypeRef, list[TypeRef] | Unknown] = {}

    def type_named(self, written: str, file: str) -> TypeRef | Unknown:
        f = self._ctx.files_by_path.get(file)
        return self._named(f, written) if f is not None else NOT_A_FILE

    def return_type(self, function: str, file: str, result: int = 0) -> TypeRef | Unknown:
        f = self._ctx.files_by_path.get(file)
        if f is None:
            return NOT_A_FILE
        alias, _, name = function.rpartition(".")
        package = self._package(f, alias or None)
        if package is None:
            return OUTSIDE
        for decl in self.files_in(package):
            rets = self._facts(decl).funcs.get(name)
            if rets:
                return self._named(decl, rets[result]) if result < len(rets) and rets[result] else NOT_A_NAME
        return UNDECLARED

    def field(self, owner: TypeRef, name: str) -> Field | Unknown:
        return self._field(owner, name, 0)

    def method(self, owner: TypeRef, name: str) -> TypeRef | Unknown:
        """For an interface: the interface, its own or one it embeds, that requires the method."""
        required = self._required_by(owner)
        return NO_METHODS if required is None else required.get(name, NOT_REQUIRED)

    def bases(self, of: TypeRef) -> list[TypeRef | Unknown] | Unknown:
        """The types a struct or an interface embeds; one of a package outside the repo, or of a directory with no Go
        file, is Unknown."""
        for f in self.files_in(of.package):
            facts = self._facts(f)
            st, iface = facts.structs.get(of.name), facts.interfaces.get(of.name)
            if st is None and iface is None:
                continue
            embedded = st.embeds if st is not None else iface.embeds or ()
            return [self._base(f, written) for written in embedded]
        return UNDECLARED

    def implementers(self, interface: TypeRef) -> list[TypeRef] | Unknown:
        """The types whose methods, as production code declares them, cover every method the interface requires."""
        if interface not in self._implementers:
            required = self._required_by(interface)
            self._implementers[interface] = NO_METHODS if not required else sorted(
                t for t, have in self._method_sets().items() if required.keys() <= have)
        return self._implementers[interface]

    def files_in(self, package: str) -> list[FileInfo]:
        """The Go files of the package whose dotted directory is `package`, in the repo's order."""
        if self._by_dir is None:
            self._by_dir = {}
            for f in self._ctx.files_by_path.values():
                if f.language == "go":
                    self._by_dir.setdefault(str(PurePosixPath(f.path).parent), []).append(f)
        return self._by_dir.get(package.replace(".", "/") or ".", [])

    def _facts(self, f: FileInfo) -> GoTypes:
        return GoTypes.of(self._ctx.facts.get(f.id))

    def _package(self, file: FileInfo, alias: str | None) -> str | None:
        """The dotted directory of the package a type reference names: the file's own when unqualified, else the one
        the alias imports, when it is a module of this repo."""
        if alias is None:
            d = str(PurePosixPath(file.path).parent)
            return "" if d == "." else d.replace("/", ".")
        spec = self._facts(file).imports.get(alias)
        if not spec:
            return None
        for mp, m in self._modules:
            if spec == mp or spec.startswith(mp + "/"):
                rel = spec[len(mp):].strip("/")
                return "/".join(p for p in (m.path, rel) if p).replace("/", ".")
        return None

    def _named(self, file: FileInfo, written: str) -> TypeRef | Unknown:
        alias, _, name = written.rpartition(".")
        package = self._package(file, alias or None)
        return TypeRef(package, name) if package is not None else OUTSIDE

    def _base(self, file: FileInfo, written: str) -> TypeRef | Unknown:
        ref = self._named(file, written)
        return ref if isinstance(ref, TypeRef) and self.files_in(ref.package) else OUTSIDE

    def _field(self, owner: TypeRef, name: str, depth: int) -> Field | Unknown:
        """A field of the struct, else the first one an embedded struct promotes with a type of the repo, depth first."""
        if depth > DEPTH:
            return TOO_DEEP
        for f in self.files_in(owner.package):
            st = self._facts(f).structs.get(owner.name)
            if st is None:
                continue
            if name in st.fields:
                return Field(self._named(f, st.fields[name]), st.fields[name], depth > 0)
            for written in st.embeds:
                inner = self._named(f, written)
                hit = self._field(inner, name, depth + 1) if isinstance(inner, TypeRef) else inner
                if isinstance(hit, Field) and isinstance(hit.type, TypeRef):
                    return hit
            return NO_FIELD
        return UNDECLARED

    def _required_by(self, interface: TypeRef) -> dict[str, TypeRef] | None:
        if interface not in self._required:
            self._required[interface] = self._requires(interface, 0)
        return self._required[interface]

    def _requires(self, owner: TypeRef, depth: int) -> dict[str, TypeRef] | None:
        """Every method an interface of the repo requires, embedded interfaces' included, by the interface that
        declares it; None when it is not an interface of the repo, embeds one from outside (`io.Reader`: its methods
        are unknown) or is a type constraint."""
        if depth > DEPTH:
            return None
        for f in self.files_in(owner.package):
            iface = self._facts(f).interfaces.get(owner.name)
            if iface is None:
                continue
            if iface.embeds is None:
                return None
            out = dict.fromkeys(iface.methods, owner)
            for written in iface.embeds:
                inner = self._named(f, written)
                more = self._requires(inner, depth + 1) if isinstance(inner, TypeRef) else None
                if more is None:
                    return None
                out = {**more, **out}
            return out
        return None

    def _method_sets(self) -> dict[TypeRef, set[str]]:
        """Each type → the methods production code declares on it: fakes and mocks implement an interface too, but
        they are not what runs."""
        if self._sets is None:
            self._sets = {}
            for f in self._ctx.files_by_path.values():
                if f.language != "go" or is_test_path(f.path):
                    continue
                d = str(PurePosixPath(f.path).parent)
                package = "" if d == "." else d.replace("/", ".")
                for recv, names in self._facts(f).methods.items():
                    self._sets.setdefault(TypeRef(package, recv), set()).update(names)
        return self._sets
