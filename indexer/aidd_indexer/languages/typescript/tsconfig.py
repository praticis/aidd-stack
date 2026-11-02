"""The `tsconfig.json` and `jsconfig.json` of a repo, read as TypeScript reads them to resolve a file's imports: the
nearest one above the file, its `extends` followed within the repo, and, where it maps no path and only refers to other
projects, the referenced one whose `files` or `include` holds the file. What an import takes from it is `paths`, with
the folder its targets are relative to, and `baseUrl`. A config another package publishes is not in the repo, so an
`extends` of one adds nothing."""

from __future__ import annotations

import json
import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..base import ResolveContext

NAMES = ("tsconfig.json", "jsconfig.json")
_KEY = "ts_configs"
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


@dataclass(frozen=True)
class Config:
    paths: tuple[tuple[str, tuple[str, ...]], ...] = ()   # pattern -> targets, as written
    paths_base: str = ""                                  # the folder the targets are relative to
    base_url: str | None = None


@dataclass
class _Parsed:
    """A config with what its `extends` gives it: each option kept with the folder of the config that writes it."""
    folder: str
    paths: dict | None = None
    paths_folder: str = ""
    base_url: str | None = None
    files: list[str] | None = None
    include: list[str] | None = None
    patterns_folder: str = ""
    references: list[str] = field(default_factory=list)


def configs(ctx: ResolveContext) -> TsConfigs:
    """The repo's configs, read once for each context that resolves an import."""
    found = ctx.extra.get(_KEY)
    if found is None:
        found = ctx.extra[_KEY] = TsConfigs(ctx.root)
    return found


class TsConfigs:
    def __init__(self, root: Path):
        self._root = root
        self._nearest: dict[str, str | None] = {}
        self._parsed: dict[str, _Parsed | None] = {}
        self._of: dict[str, Config | None] = {}

    def of(self, file: str) -> Config | None:
        """What the config that holds the file at `file` maps an import to; None where no config is above it."""
        if file not in self._of:
            self._of[file] = self._config(file)
        return self._of[file]

    def _config(self, file: str) -> Config | None:
        nearest = self._near(posixpath.dirname(file))
        parsed = self._read(nearest) if nearest else None
        if parsed is None:
            return None
        if parsed.paths is None and parsed.references:
            parsed = next((sub for sub in map(self._read, parsed.references) if sub and _holds(sub, file)), parsed)
        base = parsed.base_url if parsed.base_url is not None else parsed.paths_folder
        return Config(tuple((k, tuple(v)) for k, v in (parsed.paths or {}).items() if isinstance(v, list)), base,
                      parsed.base_url)

    def _near(self, folder: str) -> str | None:
        if folder not in self._nearest:
            here = next((posixpath.join(folder, n) if folder else n for n in NAMES
                         if (self._root / folder / n).is_file()), None)
            self._nearest[folder] = here if here or not folder else self._near(posixpath.dirname(folder))
        return self._nearest[folder]

    def _read(self, rel: str, seen: frozenset[str] = frozenset()) -> _Parsed | None:
        if rel in seen:
            return None
        if rel not in self._parsed:
            self._parsed[rel] = self._parse(rel, seen | {rel})
        return self._parsed[rel]

    def _parse(self, rel: str, seen: frozenset[str]) -> _Parsed | None:
        data = _jsonc(self._root / rel)
        if not isinstance(data, dict):
            return None
        folder = posixpath.dirname(rel)
        out = _Parsed(folder, paths_folder=folder, patterns_folder=folder)
        for base in filter(None, (self._extended(folder, e, seen) for e in _listed(data.get("extends")))):
            out = _inherit(out, base)
        return _own(out, data, folder, [r for r in (self._reference(folder, ref) for ref in _refs(data)) if r])

    def _extended(self, folder: str, written: str, seen: frozenset[str]) -> _Parsed | None:
        rel = within(folder, written)
        if not written.startswith(".") or rel.startswith(".."):
            return None
        for candidate in (rel, f"{rel}.json", posixpath.join(rel, "tsconfig.json")):
            if (self._root / candidate).is_file():
                return self._read(candidate, seen)
        return None

    def _reference(self, folder: str, written: str) -> str | None:
        rel = within(folder, written)
        if rel.startswith(".."):
            return None
        for candidate in (rel, posixpath.join(rel, "tsconfig.json")):
            if (self._root / candidate).is_file():
                return candidate
        return None


def _inherit(out: _Parsed, base: _Parsed) -> _Parsed:
    """What a config takes from one it extends, each option the latter writes; references are each config's own."""
    if base.paths is not None:
        out.paths, out.paths_folder = base.paths, base.paths_folder
    if base.base_url is not None:
        out.base_url = base.base_url
    if base.files is not None or base.include is not None:
        out.files, out.include, out.patterns_folder = base.files, base.include, base.patterns_folder
    return out


def _own(out: _Parsed, data: dict, folder: str, references: list[str]) -> _Parsed:
    options = data.get("compilerOptions") if isinstance(data.get("compilerOptions"), dict) else {}
    if isinstance(options.get("paths"), dict):
        out.paths, out.paths_folder = options["paths"], folder
    if isinstance(options.get("baseUrl"), str):
        out.base_url = within(folder, options["baseUrl"])
    if isinstance(data.get("files"), list) or isinstance(data.get("include"), list):
        out.files, out.include, out.patterns_folder = _strings(data.get("files")), _strings(data.get("include")), folder
    out.references = references
    return out


def _holds(parsed: _Parsed, file: str) -> bool:
    """Whether the config's `files` or `include` names the file; with neither, every file below it."""
    if parsed.files is None and parsed.include is None:
        return file.startswith(f"{parsed.folder}/") if parsed.folder else True
    if any(within(parsed.patterns_folder, f) == file for f in parsed.files or ()):
        return True
    return any(_glob(within(parsed.patterns_folder, p)).fullmatch(file) for p in parsed.include or ())


def _glob(pattern: str) -> re.Pattern:
    """An `include` pattern as TypeScript matches it: `**/` any folders, `*` and `?` within one name, and a last name
    with no extension or wildcard a folder whose files it all holds."""
    if not re.search(r"[.*?]", pattern.rsplit("/", 1)[-1]):
        pattern += "/**/*"
    out = re.escape(pattern).replace(r"\*\*/", "(?:[^/]+/)*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    return re.compile(out)


def within(folder: str, written: str) -> str:
    joined = posixpath.normpath(posixpath.join(folder, written))
    return "" if joined == "." else joined


def _listed(value) -> list[str]:
    return [value] if isinstance(value, str) else _strings(value) or []


def _strings(value) -> list[str] | None:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else None


def _refs(data: dict) -> list[str]:
    refs = data.get("references")
    return [r["path"] for r in refs if isinstance(r, dict) and isinstance(r.get("path"), str)] \
        if isinstance(refs, list) else []


def _jsonc(path: Path):
    """The config's JSON, with the comments and trailing commas TypeScript allows in it; None where it is no JSON."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    try:
        return json.loads(_TRAILING_COMMA.sub(r"\1", _uncommented(text)))
    except ValueError:
        return None


def _uncommented(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c == '"':
            j = _string_end(text, i)
            out.append(text[i:j])
            i = j
        elif text.startswith("//", i):
            i = text.find("\n", i) if "\n" in text[i:] else len(text)
        elif text.startswith("/*", i):
            i = text.find("*/", i) + 2 if "*/" in text[i:] else len(text)
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _string_end(text: str, i: int) -> int:
    """The index after the JSON string that starts at `i`."""
    j = i + 1
    while j < len(text) and text[j] != '"':
        j += 2 if text[j] == "\\" else 1
    return j + 1
