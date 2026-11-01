"""What a TS or JS import names: a file of the repo, found from a relative path or a path alias (`@/`, `~/`, `src/`,
`#`, `$lib`) by the usual extensions and a folder's `index.*`, or else an npm package (`node:` is the platform's)."""

from __future__ import annotations

import posixpath
import re
from pathlib import PurePosixPath
from typing import NamedTuple

from ...core.model import FileInfo
from ..base import ResolveContext

TS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".d.ts")


class Package(NamedTuple):
    name: str
    platform: bool


def module_target(ctx: ResolveContext, file: FileInfo, spec: str) -> FileInfo | Package | None:
    """The file of the repo, or the package, an import of `spec` in `file` names; None for a path that names no file."""
    if spec.startswith("."):
        return _try_paths(ctx, PurePosixPath(posixpath.normpath(str(PurePosixPath(file.path).parent / spec))))
    if spec.startswith(("@/", "~/", "src/", "#", "$lib/")) or spec == "$lib":   # `$lib`: SvelteKit's, src/lib
        tail = re.sub(r"^\$lib\b", "lib", re.sub(r"^(@/|~/|#)", "", spec))   # path alias — conventional roots,
        mod = ctx.module_by_id.get(file.module_id)       # in the file's package first (its tsconfig's `paths`),
        pkg = mod.path if mod is not None and mod.path not in ("", ".") else ""   # then the repo's
        for base in dict.fromkeys((pkg, "")):
            for root in ("src", "", "app", "lib"):
                t = _try_paths(ctx, PurePosixPath(*[p for p in (base, root, tail) if p]))
                if t:
                    return t
        return None
    if spec.startswith("node:"):
        return Package(spec, True)
    return Package("/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0], False)


def _try_paths(ctx: ResolveContext, base: PurePosixPath) -> FileInfo | None:
    """The file `base` names: as written, with the usual extensions, as a folder's `index.*` — and a `.js` written for
    a `.ts` source (`import { x } from './enum.js'`, TS with `moduleResolution: nodenext`)."""
    stem = re.sub(r"\.[mc]?jsx?$", "", str(base))
    compiled = [f"{stem}{e}" for e in (".ts", ".tsx", ".mts", ".cts")] if stem != str(base) else []
    for cand in [str(base)] + compiled + [f"{base}{e}" for e in TS_EXTS] + [f"{base}/index{e}" for e in TS_EXTS]:
        f = ctx.file_at(cand)
        if f:
            return f
    return None
