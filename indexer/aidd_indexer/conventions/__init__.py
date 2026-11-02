"""Convention registry and pipeline hook.

atlas.yaml (per tenant):

```yaml
conventions:
  - path: /workspace/<tenant>/.aidd/convention.yaml     # declarative (conventions/declarative.py)
    repos: ["orders-*", "payments-api"]                  # optional globs; default: every repo
  - id: my-company-pattern                              # entry point `aidd.conventions` or `pkg.mod:Class`
    options: {strict: true}
```

`load(specs, repo_name)` resolves the specs that apply to a repo; `apply(convs, res, rv)` runs the
annotation hooks and rules and mutates the ExtractionResult (`File.layer`, `Module.layer`,
`HttpCall.target_hint`, `Symbol.role`, `Symbol.is_entry_point`, `violations`, and `conventions` /
`architecture` — what the snapshot records). With no conventions configured the
result is untouched — the indexer's output is exactly what the language modules produced.
"""

from __future__ import annotations

import fnmatch
import importlib
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Callable

from ..core.config import ConfigError
from ..core.dispatch import DispatchRule
from ..core.scan_patterns import ScanPatterns
from ..core.model import ExtractionResult, FileInfo, ModuleInfo
from ..core.resolve import TYPE_KINDS, Resolved
from .base import Convention, ConventionContext

ENTRY_POINT_GROUP = "aidd.conventions"


def _resolve_class(ref: str) -> type[Convention]:
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        if ep.name == ref:
            return ep.load()
    if ":" in ref:
        mod, cls = ref.split(":", 1)
        return getattr(importlib.import_module(mod), cls)
    raise ConfigError(f"convention '{ref}' not found: no entry point in group '{ENTRY_POINT_GROUP}' and not a 'module:Class' path")


def load_one(spec: dict[str, Any] | str) -> Convention:
    if isinstance(spec, str):
        spec = {"path": spec} if spec.endswith((".yaml", ".yml")) else {"id": spec}
    if spec.get("path"):
        from .declarative import DeclarativeConvention
        p = Path(spec["path"])
        if not p.exists():
            raise ConfigError(f"convention file not found: {p}")
        conv: Convention = DeclarativeConvention(p)
    elif spec.get("id"):
        conv = _resolve_class(str(spec["id"]))()
        conv.id = conv.id or str(spec["id"])
    else:
        raise ConfigError(f"convention spec needs 'path' or 'id': {spec}")
    conv.configure(dict(spec.get("options") or {}))
    return conv


def load(specs: list[dict[str, Any] | str], repo_name: str) -> list[Convention]:
    out: list[Convention] = []
    for spec in specs or []:
        repos = spec.get("repos") if isinstance(spec, dict) else None
        if repos and not any(fnmatch.fnmatch(repo_name, g) for g in repos):
            continue
        out.append(load_one(spec))
    return out


def scan_patterns(convs: list[Convention]) -> ScanPatterns:
    out = ScanPatterns()
    for c in convs or []:
        out = out.merge(c.scan_patterns())
    return out


def dispatch_rules(convs: list[Convention]) -> list[DispatchRule]:
    return [r for c in convs or [] for r in c.dispatch()]


def _first(convs: list[Convention], ask: Callable[[Convention], Any],
           answered: Callable[[Any], bool] = bool) -> Any:
    """The first answer, in the conventions' order; those after it are not asked."""
    for c in convs:
        v = ask(c)
        if answered(v):
            return v
    return None


def _roles(convs: list[Convention], res: ExtractionResult, files_by_id: dict[str, FileInfo]) -> None:
    for s in res.symbols:
        f = files_by_id.get(s.file_id)
        if f is None or s.kind not in TYPE_KINDS:
            continue
        role = _first(convs, lambda c: c.role_of(s, f))
        if role is not None:
            s.role = role


def _layers(convs: list[Convention], res: ExtractionResult, ctx: ConventionContext,
            modules: dict[str, ModuleInfo]) -> None:
    for f in res.files:
        layer = _first(convs, lambda c: c.layer_of(f, modules.get(f.module_id)))
        if layer is not None:
            f.layer = layer
            ctx.file_layer[f.id] = layer


def _module_layers(res: ExtractionResult, ctx: ConventionContext, modules: dict[str, ModuleInfo]) -> None:
    """A module's layer is the layer of its files when they agree."""
    by_mod: dict[str, set[str]] = {}
    for f in res.files:
        if f.layer:
            by_mod.setdefault(f.module_id, set()).add(f.layer)
    for mid, layers in by_mod.items():
        if len(layers) == 1 and mid in modules:
            modules[mid].layer = next(iter(layers))
            ctx.module_layer[mid] = modules[mid].layer  # type: ignore[assignment]


def _targets(convs: list[Convention], res: ExtractionResult, files_by_id: dict[str, FileInfo]) -> None:
    for call in res.http_calls:
        f = files_by_id.get(call.file_id)
        if f is None:
            continue
        target = _first(convs, lambda c: c.target_of(call, f))
        if target is not None:
            call.target_hint = target


def _entry_points(convs: list[Convention], res: ExtractionResult, files_by_id: dict[str, FileInfo]) -> None:
    syms = {s.id: s for s in res.symbols}
    for s in res.symbols:
        f = files_by_id.get(s.file_id)
        if f is None or s.kind not in ("function", "method"):
            continue
        owner = syms.get(s.parent_id) if s.parent_id else None
        # False is an answer: a convention may deny what the language's heuristic says
        v = _first(convs, lambda c: c.is_entry_point(s, f, owner), lambda v: v is not None)
        if v is not None:
            s.is_entry_point = v


def apply(convs: list[Convention], res: ExtractionResult, rv: Resolved) -> None:
    if not convs:
        return
    modules = {m.id: m for m in res.modules}
    files_by_id = {f.id: f for f in res.files}
    ctx = ConventionContext(res=res, rv=rv, files_by_id=files_by_id)
    for c in convs:
        c.prepare(ctx)
    res.conventions = [c.describe() for c in convs]
    res.architecture = next((c.architecture for c in convs if c.architecture), None)
    _roles(convs, res, files_by_id)            # before entry points, which may read an owner's role
    _layers(convs, res, ctx, modules)
    _module_layers(res, ctx, modules)
    _targets(convs, res, files_by_id)
    _entry_points(convs, res, files_by_id)
    for c in convs:
        res.violations.extend(c.check(ctx))
