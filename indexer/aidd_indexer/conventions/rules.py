"""What a declarative convention's rules report: each kind of rule, as the violations it finds."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..core import ids
from ..core.model import FileInfo, RepoInfo, ViolationInfo
from .base import ConventionContext

# (file, line, message, symbol id)
Found = Iterator[tuple[FileInfo, int, str, str | None]]


def _import_target(e, ctx: ConventionContext) -> tuple[str | None, str] | None:
    """(layer, shown name) of what an import reaches: the File, or — for an import of a
    namespace, which targets its Module (C#) — the one layer of the files declaring it."""
    if e.target_label == "File":
        t = ctx.files_by_id.get(e.target_id)
        return (ctx.file_layer.get(t.id), t.path) if t is not None else None
    if e.target_label == "Module":
        layers = {ctx.file_layer.get(fid) for fid in ctx.rv.namespace_files.get(e.spec, ())}
        if len(layers) == 1:          # a namespace spread over layers says nothing about the dependency
            return next(iter(layers)), e.spec
    return None


def _forbid_import(rule: dict, ctx: ConventionContext, path_layer: dict[str, str]) -> Found:
    spec = rule["forbid_import"] or {}
    src_layer, to = spec.get("from"), set(spec.get("to") or [])
    for e in ctx.rv.imports:
        f = ctx.files_by_id.get(e.file_id)
        if f is None or ctx.file_layer.get(f.id) != src_layer:
            continue
        hit = _import_target(e, ctx)
        if hit is not None and hit[0] in to:
            yield f, e.line, f"{src_layer} imports {hit[0]} ({hit[1]})", None


def _endpoints_only_in(rule: dict, ctx: ConventionContext, path_layer: dict[str, str]) -> Found:
    allowed = set(rule["endpoints_only_in"] or [])
    for ep in ctx.res.endpoints:
        f = ctx.files_by_id.get(ep.file_id)
        if f is not None and ctx.file_layer.get(f.id) not in allowed:
            yield f, ep.line, (f"{ep.method} {ep.path} declared in layer {ctx.file_layer.get(f.id) or '(none)'}, "
                               f"allowed: {', '.join(sorted(allowed))}"), ep.handler_id


def _roles_in(rule: dict, ctx: ConventionContext, path_layer: dict[str, str]) -> Found:
    allowed_by_role = {str(k): set(v or []) for k, v in (rule["roles_in"] or {}).items()}
    for sym in ctx.res.symbols:
        allowed = allowed_by_role.get(sym.role or "")
        f = ctx.files_by_id.get(sym.file_id)
        layer = path_layer.get(sym.file_id)      # only where the layout put it, not inferred from the role
        if allowed is None or f is None or layer is None or layer in allowed:
            continue
        yield f, sym.line_start, (f"{sym.role} {sym.name} lives in layer {layer}, "
                                  f"expected: {', '.join(sorted(allowed))}"), sym.id


def _http_calls_only_in(rule: dict, ctx: ConventionContext, path_layer: dict[str, str]) -> Found:
    allowed = set(rule["http_calls_only_in"] or [])
    for c in ctx.res.http_calls:
        f = ctx.files_by_id.get(c.file_id)
        if f is not None and ctx.file_layer.get(f.id) not in allowed:
            yield f, c.line, (f"outbound {c.method} {c.path} from layer {ctx.file_layer.get(f.id) or '(none)'}, "
                              f"allowed: {', '.join(sorted(allowed))}"), c.caller_id


# A rule that names two kinds runs only the first in this order, which is not the order of the kinds' list.
KINDS = {"forbid_import": _forbid_import, "endpoints_only_in": _endpoints_only_in, "roles_in": _roles_in,
         "http_calls_only_in": _http_calls_only_in}


def _violation(convention: str, repo: RepoInfo, rule: dict[str, Any], f: FileInfo, line: int, msg: str,
               symbol_id: str | None) -> ViolationInfo:
    return ViolationInfo(
        id=ids.violation(repo.tenant, repo.name, repo.ref, convention, rule["id"], f.path, line),
        convention=convention, rule=rule["id"], severity=rule["severity"], message=msg,
        file_id=f.id, line=line, symbol_id=symbol_id, evidence=f"{repo.name}:{f.path}:{line}",
    )


def violations(convention: str, rules: list[dict[str, Any]], ctx: ConventionContext,
               path_layer: dict[str, str]) -> list[ViolationInfo]:
    """`path_layer`: the layer the convention's own layout gave each file it was asked about."""
    out: list[ViolationInfo] = []
    for rule in rules:
        kind = next((k for k in KINDS if k in rule), None)
        if kind is None:
            continue
        for f, line, msg, symbol_id in KINDS[kind](rule, ctx, path_layer):
            out.append(_violation(convention, ctx.res.repo, rule, f, line, msg, symbol_id))
    return out
