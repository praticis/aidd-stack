"""What a TS or JS import names: a file of the repo, as TypeScript resolves it with the config that holds the importing
file (`tsconfig.py`), a relative path, a pattern of its `paths` or a name below its `baseUrl`, each by the usual
extensions and a folder's `index.*`; else a conventional path alias (`@/`, `~/`, `src/`, `#`, `$lib`), which a
bundler's config declares where no config of the repo maps it; or else an npm package (`node:` is the platform's)."""

from __future__ import annotations

import posixpath
import re
from typing import NamedTuple

from ...core.model import FileInfo
from ..base import ResolveContext
from .tsconfig import Config, configs, within

TS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".d.ts")


class Package(NamedTuple):
    name: str
    platform: bool


def module_target(ctx: ResolveContext, file: FileInfo, spec: str) -> FileInfo | Package | None:
    """The file of the repo, or the package, an import of `spec` in `file` names; None for a path that names no file."""
    if spec.startswith("."):
        return _try_paths(ctx, within(posixpath.dirname(file.path), spec), folder=spec.endswith("/"))
    config = configs(ctx).of(file.path)
    found = _configured(ctx, config, spec) if config is not None else None
    if found is not None:
        return found
    if spec.startswith(("@/", "~/", "src/", "#", "$lib/")) or spec == "$lib":   # `$lib`: SvelteKit's, src/lib
        return _aliased(ctx, file, spec)
    if spec.startswith("node:"):
        return Package(spec, True)
    return Package("/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0], False)


def _configured(ctx: ResolveContext, config: Config, spec: str) -> FileInfo | None:
    """The first target of the `paths` pattern that matches `spec` to name a file; where none matches, the file `spec`
    names below `baseUrl`. A pattern that matches and names no file leaves `baseUrl` untried, as TypeScript does."""
    targets = _mapped(config.paths, spec)
    if targets is None:
        return _try_paths(ctx, within(config.base_url, spec)) if config.base_url is not None else None
    return next((f for f in (_try_paths(ctx, within(config.paths_base, t)) for t in targets) if f), None)


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


def _try_paths(ctx: ResolveContext, base: str, folder: bool = False) -> FileInfo | None:
    """The file `base` names: as written, with the usual extensions, as a folder's `index.*` — and a `.js` written for
    a `.ts` source (`import { x } from './enum.js'`, TS with `moduleResolution: nodenext`). A path written with a
    trailing `/` names a folder only."""
    index = [f"{base}/index{e}" if base else f"index{e}" for e in TS_EXTS]
    if folder:
        return next(filter(None, map(ctx.file_at, index)), None)
    stem = re.sub(r"\.[mc]?jsx?$", "", base)
    compiled = [f"{stem}{e}" for e in (".ts", ".tsx", ".mts", ".cts")] if stem != base else []
    named = [base] + compiled + [f"{base}{e}" for e in TS_EXTS] if base else []
    return next(filter(None, map(ctx.file_at, named + index)), None)

