"""Integration candidates: HTTP routes a repo EXPOSES and outbound HTTP calls it
makes with a literal (or template) path. Deterministic, tree-sitter based, no LLM.

This module only orchestrates: per-directory context (route constants, env-var names) is collected
for every file, then each parseable file is handed to the scanner its language module registers
(`LanguageSupport.http_scanner`), and last each language composes what crosses files (`BaseScanner.compose`)
from the facts the files published. What each language recognizes lives in
`languages/<lang>/http.py`; the shared expression → path machinery in `core/http_base.py`.
A committed build bundle (a minified or hash-named `.js`) is left out: its routes and calls repeat the source's.
"""

from __future__ import annotations

import re
from dataclasses import replace

from .. import languages
from . import ids
from .http_base import TEST_FILE, HttpResult, PackageContext, ScanPatterns, collect_constants, dir_of
from .paths import path_key
from .types import RepoTypes
from .http_view import RepoView
from .model import HttpEndpointInfo, ModuleInfo, RepoInfo


def _shared(types: RepoTypes | None, repo: RepoInfo, extractors: list, modules: list[ModuleInfo] | None) -> RepoTypes:
    """The type service the caller shares with its resolver, or one over these files when it shares none."""
    if types is not None:
        return types
    return RepoTypes.of_files(repo.root, [fx.file for fx in extractors], modules or [],
                              {fx.file.id: fx.facts for fx in extractors})


def extract_http(repo: RepoInfo, extractors: list, patterns: "ScanPatterns | None" = None,
                 modules: list[ModuleInfo] | None = None, types: RepoTypes | None = None) -> HttpResult:
    """`extractors` are FileExtractor objects (core/extract.py) after `.run()`; `patterns` is what the
    tenant's conventions add to the scanners (route registrars / client methods of an internal SDK); `modules`
    let an import be resolved to a package directory (Go)."""
    out = HttpResult()
    by_dir: dict[str, PackageContext] = {}
    scanners: dict[type, None] = {}
    extractors = [fx for fx in extractors if not built_bundle(fx.file.path, fx.src)]
    for fx in extractors:
        ctx = by_dir.setdefault(dir_of(fx.file.path), PackageContext(patterns))
        collect_constants(fx, ctx)
        ctx.file_facts[fx.file.path] = fx.facts
        if not TEST_FILE.search("/" + fx.file.path):
            for s in fx.symbols:
                if s.kind in ("function", "method"):
                    ctx.functions_by_name.setdefault(s.name, []).append(s)
    view = RepoView(repo, [fx.file for fx in extractors], modules, by_dir, _shared(types, repo, extractors, modules))
    for ctx in by_dir.values():
        ctx.view = view
    for fx in extractors:
        if TEST_FILE.search("/" + fx.file.path):
            continue
        ctx = by_dir[dir_of(fx.file.path)]
        lang = languages.by_id(fx.file.language)
        scanner = lang.http_scanner if lang is not None else None
        if scanner is None:
            continue
        scanners[scanner] = None
        try:
            scanner(repo, fx, ctx, out).scan()
        except Exception as e:  # noqa: BLE001 — a weird file must not stop the repo
            out.warnings.append(f"{fx.file.path}: http candidates skipped ({type(e).__name__}: {e})")
    for scanner in scanners:                     # what crosses files: composed from the summaries the files left
        try:
            scanner.compose(out, repo, view)
        except Exception as e:  # noqa: BLE001
            out.warnings.append(f"{scanner.__name__}: cross-file composition skipped ({type(e).__name__}: {e})")
    _assign_apps(out, repo, extractors, modules)
    _dedupe(out)
    return out


BUILD_HASH = re.compile(r"[.-](?=[A-Za-z0-9_-]{0,7}[0-9A-Z])[A-Za-z0-9_-]{8}\.[cm]?js$")   # main-OdxfRQdf.js, echarts.128204f2.js


def built_bundle(path: str, src: bytes) -> bool:
    """A bundler's output committed to the repo: a hash-named `.js` with long lines, or any `.js` that is mostly
    very long lines (minified, or a dev bundle of eval'd modules)."""
    if not path.endswith((".js", ".mjs", ".cjs")) or not src:
        return False
    lines = src.split(b"\n")
    longest = max(len(line) for line in lines)
    if BUILD_HASH.search(path) and longest > 500:
        return True
    return longest > 2000 and len(src) / len(lines) > 200


def _assign_apps(out: HttpResult, repo: RepoInfo, extractors: list, modules: list[ModuleInfo] | None) -> None:
    """The same route declared in two modules with a manifest (`go.mod`, `package.json`, a `.csproj`, ..) is two
    endpoints, one per module: two apps of a monorepo. A route declared once keeps the repo's id, also when it sits
    in a library an app references. A package a language implies (a Go directory) is not a module here."""
    kinds = {k for lang in languages.all() for k in (*lang.manifests.values(), *lang.manifest_suffixes.values())}
    dirs = [m.path for m in modules or [] if m.path and m.kind in kinds]
    app_of = {fx.file.id: max((d for d in dirs if fx.file.path.startswith(d + "/")), key=len, default="")
              for fx in extractors}
    apps: dict[str, set[str]] = {}
    for e in out.endpoints:
        apps.setdefault(e.id, set()).add(app_of.get(e.file_id, ""))
    out.endpoints = [_in_app(repo, e, app_of.get(e.file_id, "")) if len(apps[e.id]) > 1 else e for e in out.endpoints]


def _in_app(repo: RepoInfo, ep: HttpEndpointInfo, app: str) -> HttpEndpointInfo:
    return replace(ep, app=app, id=ids.http_endpoint(repo.tenant, repo.name, ep.method, path_key(ep.path), app))


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

