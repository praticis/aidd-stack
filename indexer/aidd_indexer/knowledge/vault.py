"""Vault files: safe names, frontmatter, owned blocks, atomic writes.

Everything here is about not damaging what people wrote: a block is replaced only between its own
markers, the text around it is kept byte for byte, and a write lands whole or not at all.
"""

from __future__ import annotations

import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

import yaml

CONTRACT = 1
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.S)


class KnowledgeError(RuntimeError):
    """A request the knowledge service refuses, with a message meant for the agent."""


def safe_name(value: str, what: str) -> str:
    """Tenant and repo names become path segments: refuse anything that could leave the vault."""
    if not isinstance(value, str) or not _NAME.match(value) or value in (".", ".."):
        raise KnowledgeError(f"invalid {what} name {value!r} (letters, digits, '.', '_', '-')")
    return value


def slugify(text: str, limit: int = 80) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > limit:
        s = s[:limit].rsplit("-", 1)[0] or s[:limit]
    return s or "insight"


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = _FRONTMATTER.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, text                       # unreadable frontmatter: treat the page as body only
    return (data if isinstance(data, dict) else {}), text[m.end():]


class _PlainDumper(yaml.SafeDumper):
    """No anchors/aliases (`first_seen: &id001 …` / `last_seen: *id001` when two keys hold the same
    object): valid YAML, but not what a person or Obsidian's properties panel expects."""

    def ignore_aliases(self, data: Any) -> bool:
        return True


def join_frontmatter(data: dict[str, Any], body: str) -> str:
    head = yaml.dump(data, Dumper=_PlainDumper, sort_keys=False, allow_unicode=True, default_flow_style=False,
                     width=1000).rstrip("\n")
    return f"---\n{head}\n---\n{body}"


def write_atomic(path: Path, text: str) -> None:
    """Whole or nothing. Keeps the mode of a file it replaces; a new one is 0644 (mkstemp would make
    it 0600, unreadable to the Obsidian MCP when that container runs as another uid)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        mode = 0o644
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def markers(block: str) -> tuple[str, str]:
    return f"<!-- aidd:{block}:start -->", f"<!-- aidd:{block}:end -->"


def replace_block(body: str, block: str, content: str, after: tuple[str, ...] = ()) -> str:
    """Put `content` between the `block` markers. Existing markers: only what is between them changes.
    Missing: the block goes right after the first of the `after` blocks present (its canonical
    position), else at the end of the page."""
    start, end = markers(block)
    wrapped = f"{start}\n{content.strip(chr(10))}\n{end}"
    i = body.find(start)
    j = body.find(end, i + len(start)) if i >= 0 else -1
    if i >= 0 and j >= 0:
        return body[:i] + wrapped + body[j + len(end):]
    for prev in after:
        _, prev_end = markers(prev)
        k = body.find(prev_end)
        if k >= 0:
            k += len(prev_end)
            return body[:k] + "\n\n" + wrapped + body[k:]
    return body.rstrip("\n") + ("\n\n" if body.strip() else "") + wrapped + "\n"
