"""The declaration file that describes a JS file of the repo, as TypeScript reads it: `a.d.ts` beside `a.js` or `a.jsx`,
`a.d.mts` beside `a.mjs`, `a.d.cts` beside `a.cjs`. An import names the JS file, which Node loads, and what a module
declares as a value is the JS's; a name the JS cannot declare, an interface or a name of the namespace an export
assignment merges, is the declaration file's."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath

DECLARED_BY = {".js": ".d.ts", ".jsx": ".d.ts", ".mjs": ".d.mts", ".cjs": ".d.cts"}


def beside(paths: Iterable[str]) -> dict[str, str]:
    """The declaration file of each JS file among `paths` that has one."""
    held = set(paths)
    out = {}
    for path in held:
        twin = DECLARED_BY.get(PurePosixPath(path).suffix)
        if twin is not None and (declaration := str(PurePosixPath(path).with_suffix(twin))) in held:
            out[path] = declaration
    return out
