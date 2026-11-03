"""The file a workspace package's entry names, as TypeScript reads its `package.json`. With `exports`, the subpath it
maps (an exact key, else the pattern with the longest prefix), by the first condition of the object, in its order, that
the resolution matches or `default`, an entry that is a file the repo lacks leaving the next to try; a subpath it does
not map is none. Without it, the subpath as a path below the package; and for the package itself, its `types`,
`typings` or `main`, then its `index`."""

from __future__ import annotations

from collections.abc import Callable, Iterator

from ...core.model import FileInfo

Find = Callable[[str, bool], "FileInfo | None"]   # a path below the package, whether it is a folder only


def entry(package: dict, subpath: str, conditions: frozenset[str], find: Find) -> FileInfo | None:
    """The file of the package for the subpath (empty for the package itself) found by `find`; None where none."""
    if package.get("exports") is not None:
        value, wildcard = _mapped(package["exports"], f"./{subpath}" if subpath else ".")
        return next(filter(None, (find(t, False) for t in _targets(value, conditions, wildcard))), None)
    if subpath:
        return find(subpath, False)
    return manifest(package, lambda written: find(written, False)) or find("", True)


def manifest(package: dict, find: Callable[[str], FileInfo | None]) -> FileInfo | None:
    """The file a folder's `package.json` names by `types`, `typings` or `main`, in that order."""
    named = (package.get(k) for k in ("types", "typings", "main"))
    return next(filter(None, (find(w) for w in named if isinstance(w, str))), None)


def _mapped(exports, key: str):
    """The value `exports` gives `key`, and what a pattern's `*` matched."""
    if not isinstance(exports, dict) or not any(k.startswith(".") for k in exports):
        return (exports, None) if key == "." else (None, None)
    if key in exports:
        return exports[key], None
    best = None
    for pattern, value in exports.items():
        head, star, tail = pattern.partition("*")
        if star and key.startswith(head) and key.endswith(tail) and len(key) >= len(head) + len(tail) \
                and (best is None or len(head) > best[0]):
            best = (len(head), value, key[len(head):len(key) - len(tail)])
    return (best[1], best[2]) if best else (None, None)


def _targets(value, conditions: frozenset[str], wildcard: str | None) -> Iterator[str]:
    """Each path `value` can name for these conditions, in the order TypeScript tries them."""
    if isinstance(value, str):
        yield value.replace("*", wildcard) if wildcard is not None else value
    elif isinstance(value, list):
        for item in value:
            yield from _targets(item, conditions, wildcard)
    elif isinstance(value, dict):
        for condition, item in value.items():
            if condition == "default" or condition in conditions:
                yield from _targets(item, conditions, wildcard)
