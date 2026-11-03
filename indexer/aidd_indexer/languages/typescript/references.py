"""The source file a project the importing file's config references builds a declaration file from. TypeScript, where a
program references a project, takes the declaration file the project would emit for a source of its (`include`) to exist
and to be that source, built or not, as an editor does: the file is in the project's `declarationDir` or `outDir`, at
the path of the source below its `rootDir`, which is the folder of the project's config where it writes none."""

from __future__ import annotations

from ...core.model import FileInfo
from ..base import ResolveContext
from .tsconfig import Project

SOURCES = {".d.ts": (".ts", ".tsx"), ".d.mts": (".mts",), ".d.cts": (".cts",)}


def source(ctx: ResolveContext, projects: tuple[Project, ...], declaration: str) -> FileInfo | None:
    """The source file one of `projects` emits the declaration file at `declaration` from; None where none does."""
    suffix = next((s for s in SOURCES if declaration.endswith(s)), None)
    if suffix is None:
        return None
    stem = declaration.removesuffix(suffix)
    for project in projects:
        prefix = f"{project.out}/" if project.out else ""
        if not stem.startswith(prefix):
            continue
        below = stem.removeprefix(prefix)
        path = f"{project.root}/{below}" if project.root else below
        hit = next((f for f in (ctx.file_at(path + ext) for ext in SOURCES[suffix])
                    if f is not None and project.holds(f.path)), None)
        if hit is not None:
            return hit
    return None
