"""Walk a repository: which files to parse, which language, which module.

Uses `git ls-files` when available (respects .gitignore), otherwise a
filesystem walk with DEFAULT_EXCLUDES. Modules are directories that hold a
build manifest; every file belongs to its nearest ancestor module, or to the
repo-root module when none exists.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath

from .. import languages
from . import ids
from .config import DEFAULT_EXCLUDES, GENERATED_SUFFIXES
from .gitinfo import tracked_files
from .model import FileInfo, ModuleInfo, RepoInfo

# Recorded as File nodes only (no symbol extraction): config, schemas, docs that other files refer to.
RECORD_ONLY_BY_EXT = {
    ".vue": "vue", ".proto": "proto", ".sql": "sql", ".yaml": "yaml", ".yml": "yaml",
    ".json": "json", ".md": "markdown", ".tf": "terraform", ".graphql": "graphql",
}


def language_of(ext: str) -> str | None:
    lang = languages.by_extension(ext)
    return lang.id if lang is not None else RECORD_ONLY_BY_EXT.get(ext)


def _manifest_kind(p: PurePosixPath) -> tuple[str, str] | None:
    """(module kind, stack tag) when `p` is a build manifest of a registered language."""
    for lang in languages.all():
        kind = lang.manifests.get(p.name) or lang.manifest_suffixes.get(p.suffix)
        if kind:
            return kind, lang.stack
    return None


def _is_excluded(rel: PurePosixPath) -> bool:
    if any(part in DEFAULT_EXCLUDES for part in rel.parts):
        return True
    return rel.name.endswith(GENERATED_SUFFIXES)


def list_files(root: Path) -> list[str]:
    tracked = tracked_files(root)
    if tracked is not None:
        rels = tracked
    else:
        rels = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDES]
            for f in filenames:
                rels.append(os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/"))
    out = []
    for r in rels:
        rp = PurePosixPath(r)
        if _is_excluded(rp):
            continue
        if (root / r).is_file():
            out.append(r)
    return sorted(out)


def discover_modules(repo: RepoInfo, rel_files: list[str]) -> tuple[list[ModuleInfo], set[str]]:
    """Return modules (nearest-manifest directories) and the detected stack."""
    modules: dict[str, ModuleInfo] = {}
    stack: set[str] = set()
    for r in rel_files:
        p = PurePosixPath(r)
        hit = _manifest_kind(p)
        if hit:
            kind, tech = hit
            stack.add(tech)
            d = str(p.parent) if str(p.parent) != "." else ""
            if d not in modules:
                modules[d] = ModuleInfo(
                    id=ids.module(repo.tenant, repo.name, repo.ref, d),
                    name=(PurePosixPath(d).name if d else repo.name),
                    path=d,
                    kind=kind,
                )
    for lang in languages.all():                       # language-implied modules (Go packages)
        lang.discover_modules(repo, rel_files, modules)
    if "" not in modules:
        modules[""] = ModuleInfo(id=ids.module(repo.tenant, repo.name, repo.ref, ""), name=repo.name, path="", kind="root")
    return sorted(modules.values(), key=lambda m: m.path), stack


def nearest_module(path: str, modules: list[ModuleInfo]) -> ModuleInfo:
    best = None
    for m in modules:
        if m.path == "" or path == m.path or path.startswith(m.path + "/"):
            if best is None or len(m.path) > len(best.path):
                best = m
    assert best is not None
    return best


def build_files(repo: RepoInfo, rel_files: list[str], modules: list[ModuleInfo]) -> list[FileInfo]:
    files: list[FileInfo] = []
    for r in rel_files:
        lang = language_of(PurePosixPath(r).suffix.lower())
        if lang is None:
            continue
        data = (Path(repo.root) / r).read_bytes()
        files.append(FileInfo(
            id=ids.file(repo.tenant, repo.name, repo.ref, r),
            path=r,
            language=lang,
            loc=data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0),
            content_hash=hashlib.sha1(data).hexdigest(),
            module_id=nearest_module(r, modules).id,
        ))
    return files
