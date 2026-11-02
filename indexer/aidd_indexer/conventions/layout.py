"""Where a declarative convention places a file: the globs of its layers, and which of its layouts a repo uses."""

from __future__ import annotations

import re
from typing import Any

from ..core.model import ModuleInfo

Layers = list[tuple[str, re.Pattern]]
Architecture = tuple[str, dict[str, Any] | None, Layers]


def glob_re(pattern: str) -> re.Pattern:
    """`**` = any depth, `*` = one segment; anchored."""
    out = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"; i += 3
        elif pattern.startswith("**", i):
            out += ".*"; i += 2
        elif pattern[i] == "*":
            out += "[^/]*"; i += 1
        else:
            out += re.escape(pattern[i]); i += 1
    return re.compile("^" + out + "$")


def layers(spec: dict | None) -> Layers:
    return [(layer, glob_re(g)) for layer, globs in (spec or {}).items() for g in (globs or [])]


def detected(detect: dict[str, Any], modules: list[str]) -> bool:
    """`modules`: any module path matches one of the globs. `together`: module names (last path
    segment) that must all exist for the same `{placeholder}` value — `["{svc}.Api", "{svc}.Core"]`
    is one service's two projects, not an unrelated `Shared.Bus.Core` library next to an `.Api`."""
    if detect.get("modules") and not any(glob_re(g).match(p) for g in detect["modules"] for p in modules):
        return False
    together = detect.get("together") or []
    if together:
        names = [p.rsplit("/", 1)[-1] for p in modules]
        bindings: set[tuple[str, ...]] | None = None
        for pat in together:
            keys = re.findall(r"\{(\w+)\}", pat)
            rx = re.compile("^" + re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>.+)", re.escape(pat)) + "$")
            found = {tuple(m.group(k) for k in keys) for n in names if (m := rx.match(n))}
            bindings = found if bindings is None else bindings & found
            if not bindings:
                return False
    return bool(detect.get("modules") or together)


def select(architectures: list[Architecture], forced: str | None,
           modules: list[ModuleInfo]) -> tuple[str | None, Layers]:
    """The layout a repo uses, with its layers: the forced one, else the first whose `detect` matches, else the one
    without `detect`."""
    if not architectures:
        return None, []
    if forced:
        return next((n, l) for n, _, l in architectures if n == forced)
    paths = [m.path for m in modules if m.path]
    for name, detect, found in architectures:          # declared order among those with `detect`
        if detect is not None and detected(detect, paths):
            return name, found
    return next(((n, l) for n, d, l in architectures if d is None), (None, []))   # the default
