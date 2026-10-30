"""Where the module a Python import names is in the repo: relative to the importing file, or under the directory its
package runs from, the root of the file's module, the repo's root or `src/`. The import resolver and the type index read
the same answer. A module is named by its path without `.py` (`app/models`, `app/__init__`); a directory of Python files
with no `__init__.py`, a namespace package, by its `__init__` all the same."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...core.model import FileInfo
    from ..base import ResolveContext


def module_bases(ctx: ResolveContext, file: FileInfo, spec: str) -> list[str]:
    """The paths, without `.py`, the module `spec` may have, in the order they are tried: an absolute import under
    the directory the file's package runs from first, then the root of the file's module, where its project declares
    itself, then the repo's root, then `src/`."""
    if spec.startswith("."):
        dots = len(spec) - len(spec.lstrip("."))
        base = PurePosixPath(file.path).parent
        for _ in range(dots - 1):
            base = base.parent
        tail = spec[dots:].replace(".", "/")
        return [str(base / tail if tail else base)]
    parts = spec.split(".")
    mod = ctx.module_by_id.get(file.module_id)
    roots = (_runs_from(ctx, file), mod.path if mod else "", "", "src")
    return [str(PurePosixPath(root) / "/".join(parts) if root else PurePosixPath("/".join(parts)))
            for root in dict.fromkeys(r for r in roots if r is not None)]


def _runs_from(ctx: ResolveContext, file: FileInfo) -> str | None:
    """The directory above the file's top regular package, or the file's own for a module of none: CPython finds the
    package by its name, or runs the file as a script, only with it on `sys.path`. None when a regular package holds
    that directory, which is then a namespace portion of the package, not a place code runs from."""
    d = PurePosixPath(file.path).parent
    while d.name and _package(ctx, d):
        d = d.parent
    if any(_package(ctx, a) for a in d.parents if a.name):
        return None
    return str(d) if d.name else ""


def _package(ctx: ResolveContext, directory: PurePosixPath) -> bool:
    return f"{directory}/__init__.py" in ctx.files_by_path


def module_file(ctx: ResolveContext, file: FileInfo, spec: str) -> FileInfo | None:
    relative = spec.startswith(".")
    for base in module_bases(ctx, file, spec):
        for cand in (f"{base}.py", f"{base}/__init__.py"):
            found = ctx.file_at(cand.lstrip("./") if relative else cand)
            if found:
                return found
    return None


def module_path(file: FileInfo) -> str:
    return file.path[:-3] if file.path.endswith(".py") else str(PurePosixPath(file.path).with_suffix(""))


class Modules:
    """The repo's modules and packages, for the type index."""

    def __init__(self, ctx: ResolveContext) -> None:
        self._ctx = ctx
        self._dirs: set[str] | None = None
        self._names: set[str] | None = None
        self._imported: dict[tuple[str, str], str | None] = {}

    def imported(self, file: FileInfo, spec: str) -> str | None:
        """The module `spec` names from `file`; None for one outside the repo."""
        key = (file.path, spec)
        if key not in self._imported:
            self._imported[key] = self._find(file, spec)
        return self._imported[key]

    def _find(self, file: FileInfo, spec: str) -> str | None:
        found = module_file(self._ctx, file, spec)
        if found is not None:
            return module_path(found)
        relative = spec.startswith(".")
        return next((f"{d}/__init__" for b in module_bases(self._ctx, file, spec)
                     if (d := b.lstrip("./") if relative else b) in self._directories()), None)

    def submodule(self, package: str, name: str) -> str | None:
        """The module `name` of the package whose `__init__` is `package`; None for a module that is no package."""
        if not package.endswith("__init__"):
            return None
        base = package[:-len("__init__")] + name
        if f"{base}.py" in self._ctx.files_by_path:
            return base
        found = f"{base}/__init__.py" in self._ctx.files_by_path or base in self._directories()
        return f"{base}/__init__" if found else None

    def holds(self, spec: str) -> bool:
        """Whether the repo has a module or a package named like the top of an absolute import it finds under no root,
        in a directory that is no package: that directory may be on the path the code runs with, ahead of the standard
        library's."""
        if self._names is None:
            files = [PurePosixPath(p) for p in self._ctx.files_by_path if p.endswith(".py")]
            packages = {f.parent for f in files if f.name == "__init__.py"}
            tops = [PurePosixPath(d) for d in self._directories()] + [f.with_suffix("") for f in files]
            self._names = {t.name for t in tops if t.parent not in packages}
        return spec.split(".")[0] in self._names

    def _directories(self) -> set[str]:
        if self._dirs is None:
            self._dirs = {str(d) for p in self._ctx.files_by_path if p.endswith(".py")
                          for d in PurePosixPath(p).parents if str(d) != "."}
        return self._dirs
