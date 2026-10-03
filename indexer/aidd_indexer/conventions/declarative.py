"""`convention.yaml` — a convention without Python.

```yaml
id: hexagonal
layers:                       # first matching glob wins; globs are repo-relative, `**` allowed
  domain:        ["internal/domain/**", "src/domain/**"]
  application:   ["internal/app/**", "src/application/**"]
  adapters-in:   ["internal/adapters/in/**", "src/api/**"]
  adapters-out:  ["internal/adapters/out/**", "src/infra/**"]
targets:                      # outbound calls made from these files talk to this service
  "internal/adapters/out/billing/**": billing
entry_points:                 # symbols whose signature contains one of these are entry points
  signature_contains: ["*fiber.Ctx"]
rules:
  - id: domain-is-pure        # File in layer `from` importing a File in one of `to`
    forbid_import: {from: domain, to: [application, adapters-in, adapters-out]}
    severity: error
  - id: routes-in-adapters-in # HttpEndpoint declared outside these layers
    endpoints_only_in: [adapters-in]
    severity: warning
  - id: clients-in-adapters-out
    http_calls_only_in: [adapters-out]
    severity: warning
```
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

import yaml

from ..core import ids
from ..core.config import ConfigError
from ..core.model import FileInfo, HttpCallInfo, ModuleInfo, SymbolInfo, ViolationInfo
from ..core.scan_patterns import ScanPatterns
from .base import Convention, ConventionContext


def _glob_re(pattern: str) -> re.Pattern:
    """`**` = any depth, `*` = one segment; anchored."""
    out = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"; i += 3
        elif pattern.startswith("**", i):
            out += ".*"; i += 2
        elif pattern[i] == "*":
            out += "[^/]*"; i += 1
        else:
            out += re.escape(pattern[i]); i += 1
    return re.compile("^" + out + "$")


class DeclarativeConvention(Convention):
    def __init__(self, path: Path):
        self.path = path
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"{path}: invalid YAML: {e}")
        self.id = str(raw.get("id") or path.parent.name)
        self.layers: list[tuple[str, re.Pattern]] = [
            (layer, _glob_re(g)) for layer, globs in (raw.get("layers") or {}).items() for g in (globs or [])
        ]
        self.targets: list[tuple[re.Pattern, str]] = [(_glob_re(g), str(svc)) for g, svc in (raw.get("targets") or {}).items()]
        self.patterns = ScanPatterns.from_dict(raw)
        ep = raw.get("entry_points") or {}
        self.entry_sig: tuple[str, ...] = tuple(ep.get("signature_contains") or [])
        self.rules: list[dict[str, Any]] = list(raw.get("rules") or [])
        for i, r in enumerate(self.rules):
            if not isinstance(r, dict) or not any(k in r for k in ("forbid_import", "endpoints_only_in", "http_calls_only_in")):
                raise ConfigError(f"{path}: rule #{i + 1} must have one of forbid_import / endpoints_only_in / http_calls_only_in")
            r.setdefault("id", f"rule{i + 1}")
            r.setdefault("severity", "warning")

    def configure(self, options: dict[str, Any]) -> None:
        pass

    def scan_patterns(self) -> ScanPatterns:
        return self.patterns

    # ---- annotation
    def layer_of(self, file: FileInfo, module: ModuleInfo | None) -> str | None:
        for layer, rx in self.layers:
            if rx.match(file.path):
                return layer
        return None

    def target_of(self, call: HttpCallInfo, file: FileInfo) -> str | None:
        for rx, svc in self.targets:
            if rx.match(file.path):
                return svc
        return None

    def is_entry_point(self, symbol: SymbolInfo, file: FileInfo) -> bool | None:
        if self.entry_sig and any(h in symbol.signature for h in self.entry_sig):
            return True
        return None

    # ---- rules
    def check(self, ctx: ConventionContext) -> list[ViolationInfo]:
        out: list[ViolationInfo] = []
        repo = ctx.res.repo
        files = ctx.files_by_id

        def emit(rule: dict, f: FileInfo, line: int, msg: str, symbol_id: str | None = None) -> None:
            out.append(ViolationInfo(
                id=ids.violation(repo.tenant, repo.name, repo.ref, self.id, rule["id"], f.path, line),
                convention=self.id, rule=rule["id"], severity=rule["severity"], message=msg,
                file_id=f.id, line=line, symbol_id=symbol_id, evidence=f"{repo.name}:{f.path}:{line}",
            ))

        for rule in self.rules:
            if "forbid_import" in rule:
                spec = rule["forbid_import"] or {}
                src_layer, to = spec.get("from"), set(spec.get("to") or [])
                for e in ctx.rv.imports:
                    if e.target_label != "File":
                        continue
                    f, t = files.get(e.file_id), files.get(e.target_id)
                    if f is None or t is None:
                        continue
                    if ctx.file_layer.get(f.id) == src_layer and ctx.file_layer.get(t.id) in to:
                        emit(rule, f, e.line, f"{src_layer} imports {ctx.file_layer[t.id]} ({t.path})")
            elif "endpoints_only_in" in rule:
                allowed = set(rule["endpoints_only_in"] or [])
                for ep in ctx.res.endpoints:
                    f = files.get(ep.file_id)
                    if f is not None and ctx.file_layer.get(f.id) not in allowed:
                        emit(rule, f, ep.line, f"{ep.method} {ep.path} declared in layer "
                             f"{ctx.file_layer.get(f.id) or '(none)'}, allowed: {', '.join(sorted(allowed))}", ep.handler_id)
            elif "http_calls_only_in" in rule:
                allowed = set(rule["http_calls_only_in"] or [])
                for c in ctx.res.http_calls:
                    f = files.get(c.file_id)
                    if f is not None and ctx.file_layer.get(f.id) not in allowed:
                        emit(rule, f, c.line, f"outbound {c.method} {c.path} from layer "
                             f"{ctx.file_layer.get(f.id) or '(none)'}, allowed: {', '.join(sorted(allowed))}", c.caller_id)
        return out
