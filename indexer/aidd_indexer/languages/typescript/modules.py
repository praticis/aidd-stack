"""What a TS or JS import names: a file of the repo, as TypeScript resolves it with the config that holds the importing
file (`tsconfig.py`), a relative path, a pattern of its `paths` or a name below its `baseUrl`, each by the usual
extensions and a folder's `index.*`; else a conventional path alias (`@/`, `~/`, `src/`, `#`, `$lib`), which a
bundler's config declares where no config of the repo maps it; else the entry of a package the repo's own workspace
declares or a local dependency links (`workspaces.py`), which its `package.json` names as TypeScript reads it
(`exports.py`), and that package alone, marked local, where its entry is a build the clone lacks; or else an npm package
(`node:` is the platform's). A file a project the config references emits as a declaration is that project's source
(`references.py`), wherever the path comes from."""

from __future__ import annotations

import posixpath
import re
from typing import NamedTuple

from ...core.model import FileInfo
from ..base import ResolveContext
from .exports import entry, manifest
from .references import source
from .tsconfig import Config, Project, configs, within
from .workspaces import package_name, workspaces

CONDITIONS = frozenset({"types", "import"})
TS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".d.ts")


class Package(NamedTuple):
    name: str
    platform: bool
    local: bool = False             # a package the repo holds, whose entry is a build the clone lacks


def module_target(ctx: ResolveContext, file: FileInfo, spec: str) -> FileInfo | Package | None:
    """The file of the repo, or the package, an import of `spec` in `file` names; None for a path that names no file."""
    config = configs(ctx).of(file.path)
    projects = config.projects if config is not None else ()
    if spec.startswith("."):
        return _try_paths(ctx, within(posixpath.dirname(file.path), spec), spec.endswith("/"), projects)
    found = _configured(ctx, config, spec) if config is not None else None
    if found is not None:
        return found
    if spec.startswith(("@/", "~/", "src/", "#", "$lib/")) or spec == "$lib":   # `$lib`: SvelteKit's, src/lib
        return _aliased(ctx, file, spec)
    if spec.startswith("node:"):
        return Package(spec, True)
    found = _workspace(ctx, file, spec, config)
    if found is not None:
        return found
    return Package("/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0], False)


def _workspace(ctx: ResolveContext, file: FileInfo, spec: str, config: Config | None) -> FileInfo | Package | None:
    """The file a package the repo holds gives an import of `spec`, or that package where its entry is a build the repo
    lacks; None where the repo holds no package by that name."""
    name, subpath = package_name(spec)
    spaces = workspaces(ctx)
    folder = spaces.member(file.path, name)
    if folder is None:
        return None
    found = entry(spaces.packages[folder], subpath, CONDITIONS | frozenset(config.conditions if config else ()),
                  lambda written, whole: _try_paths(ctx, within(folder, written), whole,
                                                    config.projects if config else ()))
    return found or Package(name, False, True)


def _configured(ctx: ResolveContext, config: Config, spec: str) -> FileInfo | None:
    """The first target of the `paths` pattern that matches `spec` to name a file; where none matches, the file `spec`
    names below `baseUrl`. A pattern that matches and names no file leaves `baseUrl` untried, as TypeScript does."""
    targets = _mapped(config.paths, spec)
    if targets is None:
        return _try_paths(ctx, within(config.base_url, spec), False, config.projects) \
            if config.base_url is not None else None
    return next((f for f in (_try_paths(ctx, within(config.paths_base, t), False, config.projects)
                             for t in targets) if f), None)


def _mapped(paths: tuple[tuple[str, tuple[str, ...]], ...], spec: str) -> list[str] | None:
    """The targets of the pattern that matches `spec`, an exact one first, else the one with the longest prefix, its
    `*` replaced by what it matched; None where none matches."""
    exact = next((targets for pattern, targets in paths if pattern == spec), None)
    if exact is not None:
        return list(exact)
    best: tuple[str, str, tuple[str, ...]] | None = None
    for pattern, targets in paths:
        head, star, tail = pattern.partition("*")
        if star and len(spec) >= len(head) + len(tail) and spec.startswith(head) and spec.endswith(tail) \
                and (best is None or len(head) > len(best[0])):
            best = (head, tail, targets)
    if best is None:
        return None
    head, tail, targets = best
    return [t.replace("*", spec[len(head):len(spec) - len(tail)], 1) for t in targets]


def _aliased(ctx: ResolveContext, file: FileInfo, spec: str) -> FileInfo | None:
    """The file a conventional alias names below the usual roots, of the file's package first, then of the repo."""
    tail = re.sub(r"^\$lib\b", "lib", re.sub(r"^(@/|~/|#)", "", spec))
    mod = ctx.module_by_id.get(file.module_id)
    pkg = mod.path if mod is not None and mod.path not in ("", ".") else ""
    for base in dict.fromkeys((pkg, "")):
        for root in ("src", "", "app", "lib"):
            found = _try_paths(ctx, "/".join(p for p in (base, root, tail) if p))
            if found:
                return found
    return None


def _try_paths(ctx: ResolveContext, base: str, folder: bool = False,
               projects: tuple[Project, ...] = ()) -> FileInfo | None:
    """The file `base` names: as written, with the usual extensions, as a folder's entry — and a `.js` written for a
    `.ts` source or its declaration file (`import { x } from './enum.js'`, TS with `moduleResolution: nodenext`). A path
    written with a trailing `/` names a folder only."""
    return _folder(ctx, base, projects) if folder else _file(ctx, base, projects) or _folder(ctx, base, projects)


def _file(ctx: ResolveContext, base: str, projects: tuple[Project, ...]) -> FileInfo | None:
    stem = re.sub(r"\.[mc]?jsx?$", "", base)
    compiled = [f"{stem}{e}" for e in (".ts", ".tsx", ".mts", ".cts", ".d.ts", ".d.mts", ".d.cts")] \
        if stem != base else []
    named = [base] + compiled + [f"{base}{e}" for e in TS_EXTS] if base else []
    return _first(ctx, named, projects)


def _first(ctx: ResolveContext, names: list[str], projects: tuple[Project, ...]) -> FileInfo | None:
    """The first of `names` that is a file of the repo, where the declaration file a project the config references
    emits is its source, though the build is there too."""
    return next(filter(None, (source(ctx, projects, n) or ctx.file_at(n) for n in names)), None)


def _folder(ctx: ResolveContext, base: str, projects: tuple[Project, ...]) -> FileInfo | None:
    """The file a folder gives an import: what its `package.json` names by `types`, `typings` or `main`, as a file or as
    a folder's `index`, else its own `index`."""
    package = workspaces(ctx).packages.get(base)
    named = manifest(package, lambda written: _file(ctx, within(base, written), projects)
                     or _index(ctx, within(base, written), projects)) if package is not None else None
    return named or _index(ctx, base, projects)


def _index(ctx: ResolveContext, base: str, projects: tuple[Project, ...]) -> FileInfo | None:
    return _first(ctx, [f"{base}/index{e}" if base else f"index{e}" for e in TS_EXTS], projects)
