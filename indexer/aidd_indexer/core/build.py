"""Which indexer wrote a snapshot — the version plus a fingerprint of the code that shapes the graph.

`INDEXER_VERSION` moves when someone remembers to bump it; a change to a resolver that ships without the
bump would leave every snapshot as it was (the refresh only re-indexes what changed). The fingerprint
closes that gap: a hash of the files that decide what the graph holds — the pipeline (`core/`), the
language modules (`languages/`), the convention framework (`conventions/`), `cli.py` — and of the
convention packages installed under the `aidd.conventions` entry point. Not the MCP servers (`mcp/`,
`knowledge/`): they read the graph, they do not shape it.

    0.2.14+3f9a1c0be27d

A snapshot whose build differs is re-indexed by the next refresh, so reinstalling the stack is enough.
"""

from __future__ import annotations

import functools
import hashlib
from importlib.metadata import entry_points
from pathlib import Path

from .. import INDEXER_VERSION

PACKAGE = Path(__file__).resolve().parent.parent
SHAPES_THE_GRAPH = ("__init__.py", "cli.py", "core", "languages", "conventions")
SUFFIXES = (".py", ".scm", ".yaml", ".yml")


def fingerprint(root: Path, parts: tuple[str, ...] = SHAPES_THE_GRAPH, extra: list[tuple[str, bytes]] = ()) -> str:
    """sha256 over (relative path, content) of the source files under `parts`, in a stable order."""
    h = hashlib.sha256()
    files: list[Path] = []
    for part in parts:
        p = root / part
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files += [f for f in p.rglob("*") if f.is_file() and f.suffix in SUFFIXES and "__pycache__" not in f.parts]
    for f in sorted(files):
        h.update(f.relative_to(root).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    for name, data in sorted(extra):
        h.update(name.encode() + b"\0" + data + b"\0")
    return h.hexdigest()[:12]


def _convention_packages() -> list[tuple[str, bytes]]:
    """Source of the installed convention extensions (their rules and roles change the graph too)."""
    out: list[tuple[str, bytes]] = []
    for ep in entry_points(group="aidd.conventions"):
        dist = ep.dist
        for f in (dist.files or []) if dist is not None else []:
            if f.suffix in SUFFIXES:
                try:
                    out.append((f"{dist.name}/{f.as_posix()}", Path(dist.locate_file(f)).read_bytes()))
                except OSError:
                    continue
    return out


@functools.lru_cache(maxsize=1)
def indexer_build() -> str:
    return f"{INDEXER_VERSION}+{fingerprint(PACKAGE, extra=_convention_packages())}"
