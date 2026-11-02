"""What a type's declaration says: its header, read from the source up to its body, the simple names of its bases, and
its ancestors through the bases the repo declares."""

from __future__ import annotations

import re
from pathlib import Path

from ..core.extract import strip_attributes
from ..core.model import FileInfo, SymbolInfo


def _split_top(text: str) -> list[str]:
    """Split on commas outside (), <>, []."""
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    return parts + [cur]


def _top_level_colon(h: str) -> int | None:
    depth = 0
    for i, ch in enumerate(h):
        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth -= 1
        elif ch == ":" and depth == 0:
            return i
    return None


def _base_list(h: str) -> str:
    """The text of the base list: after `extends`/`implements`, or after the top-level `:` and before `where`."""
    m = re.search(r"\b(?:extends|implements)\b(.*)", h)
    if m:
        return re.sub(r"\b(?:extends|implements)\b", ",", m.group(1))
    idx = _top_level_colon(h)
    if idx is None:
        return ""
    text = h[idx + 1:]
    if not text.strip():                                               # Python: `class X(A, B):`
        pm = re.search(r"\bclass\s+\w+\s*\((.*)\)\s*$", h[:idx])
        text = pm.group(1) if pm else ""
    return re.split(r"\bwhere\b", text)[0]


def _simple_name(part: str) -> str | None:
    name = re.sub(r"[<(].*$", "", part.strip()).strip().rstrip("?").split(".")[-1]
    return name if re.fullmatch(r"[A-Za-z_]\w*", name) and "=" not in part else None


def base_names(header: str) -> list[str]:
    """Simple names in a type declaration's base list: C# `class X(..) : A<T>, B where T : C`,
    TS/Java `class X extends A implements B, C`, Python `class X(A, B):`."""
    parts = _split_top(_base_list(strip_attributes(header.split("{", 1)[0])))
    return [name for name in map(_simple_name, parts) if name is not None]


class Declarations:
    """The declarations of one repo's types. Made for one preparation of a convention: the daemon indexes many refs in
    one process, and a path holds other code at another commit."""

    def __init__(self, root: Path, files_by_id: dict[str, FileInfo], types: list[SymbolInfo]):
        self._root = root
        self._files = files_by_id
        self._sources: dict[str, list[str]] = {}
        self._headers: dict[str, str] = {}
        self._by_name: dict[str, list[SymbolInfo]] = {}
        for s in types:
            self._by_name.setdefault(s.name, []).append(s)
        self._bases = {s.id: base_names(self._read(s)) for s in types}

    def header(self, s: SymbolInfo) -> str:
        if s.id not in self._headers:
            self._headers[s.id] = self._read(s)
        return self._headers[s.id]

    def ancestors(self, s: SymbolInfo, seen: set[str]) -> set[str]:
        out: set[str] = set()
        for b in self._bases.get(s.id, []):
            out.add(b)
            for t in self._by_name.get(b, []):     # an in-repo base passes its own bases on
                if t.id not in seen:
                    out |= self.ancestors(t, seen | {t.id})
        return out

    def _read(self, s: SymbolInfo) -> str:
        f = self._files.get(s.file_id)
        if f is None:
            return s.signature
        lines = self._lines(f)[s.line_start - 1: s.line_start + 14] or [s.signature]
        text = ""
        for ln in lines:                     # the declaration up to its body (base lists may span lines)
            text += " " + ln
            if "{" in ln or ln.rstrip().endswith(";"):
                break
        return " ".join(text.split())

    def _lines(self, f: FileInfo) -> list[str]:
        if f.id not in self._sources:
            try:
                self._sources[f.id] = (self._root / f.path).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                self._sources[f.id] = []
        return self._sources[f.id]
