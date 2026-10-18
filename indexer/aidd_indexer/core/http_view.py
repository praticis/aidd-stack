"""What a scanner may know about the rest of the repository while it reads one file: the constants every directory
defines (`PackageContext`, collected before any file is scanned) and where an import points — a file or a package
directory —, resolved by each language's `resolve_import`, the same resolution the `Resolver` gives `IMPORTS`.
Data only: a scanner never reads another file's tree (F1.13).
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from .. import languages
from ..languages.base import ResolveContext
from .model import FileInfo, ModuleInfo, RepoInfo

if TYPE_CHECKING:
    from .http_base import PackageContext


class RepoView:
    def __init__(self, repo: RepoInfo, files: list[FileInfo], modules: list[ModuleInfo] | None,
                 contexts: dict[str, "PackageContext"]):
        self.contexts = contexts
        self._repo, self._files, self._modules = repo, files, modules or []
        self._ctx: ResolveContext | None = None
        self._setup: set[str] = set()
        self._memo: dict[tuple[str, str], str | None] = {}
        self._paths: set[str] | None = None
        self._classes: dict[str, list["PackageContext"]] | None = None

    def _context(self, language: str) -> ResolveContext:
        if self._ctx is None:
            mods = self._modules
            self._ctx = ResolveContext(Path(self._repo.root), {f.path: f for f in self._files}, {m.path: m for m in mods},
                                       {m.id: m for m in mods}, {f.id: f for f in self._files}, {})
        lang = languages.by_id(language)
        if lang is not None and lang.id not in self._setup:
            self._setup.add(lang.id)
            lang.resolve_setup(self._ctx)
        return self._ctx

    def resolve(self, file: FileInfo, spec: str) -> str | None:
        """Repo path of the file or package directory that `spec`, imported by `file`, names; None for a package
        from outside the repo or an import that does not resolve."""
        key = (file.path, spec)
        if key not in self._memo:
            lang = languages.by_id(file.language)
            ctx = self._context(file.language)
            target = lang.resolve_import(ctx, file, spec, lambda *_: "") if lang is not None else None
            path = None
            if target is not None:
                tid, label = target
                if label == "File" and tid in ctx.files_by_id:
                    path = ctx.files_by_id[tid].path
                elif label == "Module" and tid in ctx.module_by_id:
                    path = ctx.module_by_id[tid].path
            self._memo[key] = path
        return self._memo[key]

    def constants(self, path: str) -> "PackageContext | None":
        """The constants of the package directory `path`, or of the directory of the file `path`."""
        if self._paths is None:
            self._paths = {f.path for f in self._files}
        return self.contexts.get(str(PurePosixPath(path).parent) if path in self._paths else path or ".")

    def classes_named(self, name: str) -> list["PackageContext"]:
        """The directories that define a class `name` (`PackageContext.classes`): a base named in another file is
        looked up by its name when the one class of that name in the repo is it."""
        if self._classes is None:
            self._classes = {}
            for ctx in self.contexts.values():
                for cname in ctx.classes:
                    self._classes.setdefault(cname, []).append(ctx)
        return self._classes.get(name, [])
