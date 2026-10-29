"""Where the module a Python import names is in the repo: relative to the importing file, or under the root of the
file's module, the repo's root or `src/`. The import resolver and the type index read the same answer. A module is
named by its path without `.py` (`app/models`, `app/__init__`); a directory of Python files with no `__init__.py`, a
namespace package, by its `__init__` all the same."""

from __future__ import annotations

import sys
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...core.model import FileInfo
    from ..base import ResolveContext


def module_bases(ctx: ResolveContext, file: FileInfo, spec: str) -> list[str]:
    """The paths, without `.py`, the module `spec` may have, in the order they are tried: an absolute import under
    the root of the file's module first, the nearest evidence of where its project runs from, then the repo's root,
    then `src/`."""
    if spec.startswith("."):
        dots = len(spec) - len(spec.lstrip("."))
        base = PurePosixPath(file.path).parent
        for _ in range(dots - 1):
            base = base.parent
        tail = spec[dots:].replace(".", "/")
        return [str(base / tail if tail else base)]
    parts = spec.split(".")
    mod = ctx.module_by_id.get(file.module_id)
    return [str(PurePosixPath(root) / "/".join(parts) if root else PurePosixPath("/".join(parts)))
            for root in dict.fromkeys((mod.path if mod else "", "", "src"))]


def module_file(ctx: ResolveContext, file: FileInfo, spec: str) -> FileInfo | None:
    relative = spec.startswith(".")
    for base in module_bases(ctx, file, spec):
        for cand in (f"{base}.py", f"{base}/__init__.py"):
            found = ctx.file_at(cand.lstrip("./") if relative else cand)
            if found:
                return found
    return None


def module_path(file: FileInfo) -> str:
    return str(PurePosixPath(file.path).with_suffix(""))


class Modules:
    """The repo's modules and packages, for the type index."""

    def __init__(self, ctx: ResolveContext) -> None:
        self._ctx = ctx
        self._dirs: set[str] | None = None
        self._names: set[str] | None = None

    def imported(self, file: FileInfo, spec: str) -> str | None:
        """The module `spec` names from `file`; None for one outside the repo."""
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
        """Whether the repo has a module or a package named like the top of an absolute import it finds under no root:
        the directory above it may be on the path the code runs with. The standard library's never is the repo's."""
        if self._names is None:
            self._names = {PurePosixPath(d).name for d in self._directories()} | \
                {PurePosixPath(p).stem for p in self._ctx.files_by_path if p.endswith(".py")}
        top = spec.split(".")[0]
        return top in self._names and top not in sys.stdlib_module_names

    def _directories(self) -> set[str]:
        if self._dirs is None:
            self._dirs = {str(d) for p in self._ctx.files_by_path if p.endswith(".py")
                          for d in PurePosixPath(p).parents if str(d) != "."}
        return self._dirs
