"""Manifests → what a repo publishes and what it requires (ROADMAP F0.5.1).

Each language parses its own manifest (`LanguageSupport.manifest_deps`); this module only walks the
repo, normalizes names per ecosystem and de-duplicates. The result lands on the `Snapshot`
(`provides[]`, `requires[]`) and the linker joins them across repos of a tenant into
`Service -[:DEPENDS_ON]-> Service` — the "internal package" dependency that HTTP scanning cannot see.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from .. import languages
from .model import ManifestDep, ManifestProvide, RepoInfo


def normalize(ecosystem: str, name: str) -> str:
    n = name.strip().strip('"\'').lower()
    if ecosystem == "pypi":
        n = n.replace("_", "-").replace(".", "-")
    return n


def _language_for_manifest(p: PurePosixPath):
    for lang in languages.all():
        if p.name in lang.manifests or p.suffix in lang.manifest_suffixes:
            return lang
    return None


def collect_manifest_deps(repo: RepoInfo, rel_files: list[str]) -> tuple[list[ManifestProvide], list[ManifestDep]]:
    provides: dict[str, ManifestProvide] = {}
    requires: dict[tuple[str, str], ManifestDep] = {}
    for rel in rel_files:
        p = PurePosixPath(rel)
        lang = _language_for_manifest(p)
        if lang is None:
            continue
        try:
            text = (Path(repo.root) / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        names, deps = lang.manifest_deps(rel, text)
        for n in names:
            key = normalize(lang.ecosystem, n)
            if key:
                provides.setdefault(f"{lang.ecosystem}:{key}", ManifestProvide(lang.ecosystem, key, rel))
        for n, v in deps:
            key = normalize(lang.ecosystem, n)
            if key:
                requires.setdefault((f"{lang.ecosystem}:{key}", rel), ManifestDep(lang.ecosystem, key, v.strip(), rel))
    return sorted(provides.values(), key=lambda x: (x.ecosystem, x.name)), \
        sorted(requires.values(), key=lambda x: (x.ecosystem, x.name, x.manifest))
