"""What a type's declaration says: its header, read from the source up to its body, the simple names of its bases, and
its ancestors through the bases the repo declares."""

from __future__ import annotations

import re
from pathlib import Path

from ..core.extract import strip_attributes
from ..core.model import FileInfo, SymbolInfo

_KEYWORD = r"\b(?:class|interface|struct|record|type)\s+"


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


def _declaring(name: str | None) -> re.Pattern:
    """The words that declare a type: by its whole name when it is known."""
    return re.compile(_KEYWORD + (re.escape(name) + r"\b" if name else r"\w"))


def _after_angles(h: str, i: int) -> int:
    """The index past the `>` that closes the `<` at `i`; an arrow's `>` closes nothing."""
    depth = 0
    for j in range(i, len(h)):
        if h[j] == "<":
            depth += 1
        elif h[j] == ">" and h[j - 1] != "=":
            depth -= 1
            if depth == 0:
                return j + 1
    return len(h)


def _without_type_parameters(h: str) -> str:
    """A constraint's `extends` (`class R<T extends X>`) is no base."""
    m = re.search(r"\b(?:class|interface)\s+\w+\s*<", h)
    return h if m is None else h[:m.end() - 1] + h[_after_angles(h, m.end() - 1):]


def _python_bases(h: str) -> str:
    """The text between the parentheses after `class X`, whatever follows them on its line."""
    m = re.search(r"\bclass\s+\w+\s*(?:\[[^\]]*\])?\s*\(", h)
    if m is None:
        return ""
    depth = 0
    for j in range(m.end() - 1, len(h)):
        depth += (h[j] in "([{") - (h[j] in ")]}")
        if depth == 0:
            return h[m.end():j]
    return h[m.end():]


def _base_list(h: str) -> str:
    """The text of the base list: after `extends`/`implements`, or after the top-level `:` and before `where`."""
    m = re.search(r"\b(?:extends|implements)\b(.*)", _without_type_parameters(h))
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
    """A keyword argument (`metaclass=Meta`) is no base; an arrow in a type argument (`Base<{ f: () => void }>`) is."""
    written = re.sub(r"[<(].*$", "", part.strip().rstrip(";"))
    name = written.strip().rstrip("?").split(".")[-1]
    return name if re.fullmatch(r"[A-Za-z_]\w*", name) and "=" not in written else None


def base_names(header: str, language: str | None = None, name: str | None = None,
               declaring: re.Pattern | None = None) -> list[str]:
    """Simple names in a type declaration's base list: C# `class X(..) : A<T>, B where T : C`,
    TS/Java `class X extends A implements B, C`, Python `class X(A, B):`. Read from the words that declare the type
    (`declaring`, else made from `name`), past its attributes and decorators."""
    m = (declaring or _declaring(name)).search(header)
    h = header[m.start():] if m else header
    text = _python_bases(h) if language == "python" else _base_list(strip_attributes(h[:_body_at(h)]))
    return [n for n in map(_simple_name, _split_top(text)) if n is not None]


def _declaring_line(source: list[str], s: SymbolInfo, rx: re.Pattern) -> int:
    """The line that declares the type by its name (`rx`), within the symbol's lines; else its first line."""
    return next((i for i in range(s.line_start - 1, min(s.line_end, len(source))) if rx.search(source[i])),
                s.line_start - 1)


def _body_at(h: str) -> int:
    """The index of the `{` that opens the body: the first outside the type parameters' `<>` (a `= {}` default)."""
    depth = 0
    for i, ch in enumerate(h):
        if ch == "<":
            depth += 1
        elif ch == ">" and h[i - 1] != "=" and depth:
            depth -= 1
        elif ch == "{" and depth == 0:
            return i
    return len(h)


def _code(line: str, language: str | None) -> str:
    """The line without its comment, nor a C# directive (`#pragma`) between the base list and the body."""
    if language == "python":
        return re.sub(r"#.*$", "", line)
    if language == "csharp" and line.lstrip().startswith("#"):
        return ""
    return re.sub(r"(?:^|\s)//.*$", "", re.sub(r"/\*.*?\*/", " ", line))


def _braced(text: str, line: str) -> bool:
    """Complete at its body's `{` or at the `;` that ends it."""
    return _body_at(text) < len(text) or line.rstrip().endswith(";")


def _python_header(text: str, line: str) -> bool:
    """Complete at the header's colon."""
    return _top_level_colon(text) is not None


def _go_declaration(text: str, line: str) -> bool:
    """Complete at the first `{` outside `()` and `[]`, or, these balanced, at the end of its line, where Go inserts a
    semicolon (`type X []Y`). Only `()` and `[]` count: a channel's `<-` leaves no `<` to close."""
    depth = 0
    for ch in text:
        depth += (ch in "([") - (ch in ")]")
        if ch == "{" and depth == 0:
            return True
    return depth == 0


_COMPLETE = {"python": _python_header, "go": _go_declaration}


def _to_body(lines: list[str], language: str | None) -> list[str]:
    """A declaration's lines, up to the one that completes it in its language."""
    complete = _COMPLETE.get(language or "", _braced)
    out: list[str] = []
    for ln in lines:
        out.append(_code(ln, language))
        if complete(" ".join(out), out[-1]):
            break
    return out


class Declarations:
    """The declarations of one repo's types. Made for one preparation of a convention: the daemon indexes many refs in
    one process, and a path holds other code at another commit."""

    def __init__(self, root: Path, files_by_id: dict[str, FileInfo], types: list[SymbolInfo]):
        self._root = root
        self._files = files_by_id
        self._sources: dict[str, list[str]] = {}
        self._headers: dict[str, list[str]] = {}
        self._bases: dict[str, list[str]] = {}
        self._by_name: dict[str, list[SymbolInfo]] = {}
        self._patterns: dict[str, re.Pattern] = {}       # compiled once a name: one per type overruns re's cache
        self._above: dict[str, frozenset[str]] = {}
        for s in types:
            self._by_name.setdefault(s.name, []).append(s)
        # an id declared more than once (a C# partial type) has the bases of every declaration
        for s in types:
            header = self._read(s)
            self._headers.setdefault(s.id, []).append(header)
            names = self._bases.setdefault(s.id, [])
            names += [n for n in base_names(header, self._language(s), s.name, self._pattern(s.name))
                      if n not in names]

    def headers(self, s: SymbolInfo) -> list[str]:
        return self._headers.get(s.id, [])

    def ancestors(self, s: SymbolInfo) -> set[str]:
        """The names above the type: its bases, and the names above each."""
        out: set[str] = set()
        for b in self._bases.get(s.id, []):
            out.add(b)
            out |= self._names_above(b)
        return out

    def _names_above(self, name: str) -> frozenset[str]:
        """The bases of the repo's types of that name, and theirs in turn, worked out once a name: by path a lattice
        of mixins takes exponential time, and by type a group of homonyms (Django's `Migration`) is walked again for
        each type that reaches it."""
        if name not in self._above:
            out: set[str] = set()
            todo, walked = [name], {name}
            while todo:
                for t in self._by_name.get(todo.pop(), []):     # an in-repo base passes its own bases on
                    for b in self._bases.get(t.id, []):
                        out.add(b)
                        if b not in walked:
                            walked.add(b)
                            todo.append(b)
            self._above[name] = frozenset(out)
        return self._above[name]

    def _pattern(self, name: str) -> re.Pattern:
        if name not in self._patterns:
            self._patterns[name] = _declaring(name)
        return self._patterns[name]

    def _language(self, s: SymbolInfo) -> str | None:
        f = self._files.get(s.file_id)
        return f.language if f is not None else None

    def _read(self, s: SymbolInfo) -> str:
        """The attributes and decorators above the declaration, then up to 15 of its lines, to its body."""
        f = self._files.get(s.file_id)
        if f is None:
            return s.signature
        source = self._lines(f)
        at = _declaring_line(source, s, self._pattern(s.name))
        lines = source[s.line_start - 1: at] + _to_body(source[at: at + 15], f.language)
        return " ".join(" ".join(lines or [s.signature]).split())

    def _lines(self, f: FileInfo) -> list[str]:
        if f.id not in self._sources:
            try:
                # bytes split by "\n" alone, as the extraction reads and numbers them: read_text() turns a lone "\r"
                # into a line, and splitlines() also breaks at "\x85" or "\u2028"
                self._sources[f.id] = (self._root / f.path).read_bytes().decode("utf-8", errors="replace").split("\n")
            except OSError:
                self._sources[f.id] = []
        return self._sources[f.id]
