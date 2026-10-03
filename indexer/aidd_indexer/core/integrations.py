"""Integration candidates (ROADMAP F0.4): HTTP routes a repo EXPOSES and outbound HTTP calls it
makes with a literal (or template) path. Deterministic, tree-sitter based, no LLM.

This module only orchestrates: per-directory context (route constants, env-var names) is collected
for every file, then each parseable file is handed to the scanner its language module registers
(`LanguageSupport.http_scanner`). What each language recognizes lives in
`languages/<lang>/http.py`; the shared expression → path machinery in `core/http_base.py`.
"""

from __future__ import annotations

from .. import languages
from .http_base import TEST_FILE, HttpResult, PackageContext, ScanPatterns, collect_constants, dir_of
from .model import RepoInfo


def extract_http(repo: RepoInfo, extractors: list, patterns: "ScanPatterns | None" = None) -> HttpResult:
    """`extractors` are FileExtractor objects (core/extract.py) after `.run()`; `patterns` is what the
    tenant's conventions add to the scanners (route registrars / client methods of an internal SDK)."""
    out = HttpResult()
    by_dir: dict[str, PackageContext] = {}
    for fx in extractors:
        ctx = by_dir.setdefault(dir_of(fx.file.path), PackageContext(patterns))
        collect_constants(fx, ctx)
        if not TEST_FILE.search("/" + fx.file.path):
            for s in fx.symbols:
                if s.kind in ("function", "method"):
                    ctx.functions_by_name.setdefault(s.name, []).append(s)
    for fx in extractors:
        if TEST_FILE.search("/" + fx.file.path):
            continue
        ctx = by_dir[dir_of(fx.file.path)]
        lang = languages.by_id(fx.file.language)
        scanner = lang.http_scanner if lang is not None else None
        if scanner is None:
            continue
        try:
            scanner(repo, fx, ctx, out).run()
        except Exception as e:  # noqa: BLE001 — a weird file must not stop the repo
            out.warnings.append(f"{fx.file.path}: http candidates skipped ({type(e).__name__}: {e})")
    _dedupe(out)
    return out


def _dedupe(out: HttpResult) -> None:
    seen: set[str] = set()
    eps = []
    for e in out.endpoints:
        if e.id in seen:
            continue
        seen.add(e.id)
        eps.append(e)
    out.endpoints = eps
    seen.clear()
    calls = []
    for c in out.calls:
        if c.id in seen:
            continue
        seen.add(c.id)
        calls.append(c)
    out.calls = calls

