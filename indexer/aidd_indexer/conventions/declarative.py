"""`convention.yaml` — a convention without Python.

```yaml
id: hexagonal
roles:                        # WHAT an element is, wherever it lives (types only; first match wins)
  use-case:   {extends: [UseCase], layer: application}   # a name in the base list (also via in-repo bases)
  repository: {name: ["*Repository"], layer: adapters-out}   # glob on the type name
  client:     {declares: ["(HttpClient "]}             # substring of the declaration header
layers:                       # WHERE: first matching glob wins; globs are repo-relative, `**` allowed
  domain:        ["internal/domain/**", "src/domain/**"]
  application:   ["internal/app/**", "src/application/**"]
  adapters-in:   ["internal/adapters/in/**", "src/api/**"]
  adapters-out:  ["internal/adapters/out/**", "src/infra/**"]
architectures:                # optional: one `layers` map per layout, the first whose `detect` matches a
  modular:                    # module path wins (or `options: {architecture: x}`); one without `detect` is the default.
    detect: {together: ["{svc}.Api", "{svc}.Domain"]}  # module names, same {svc} (or `modules: [globs]` on paths).
                                                       # Top-level `layers` are a fallback for every layout,
    layers: {domain: ["**/*.Domain/**"]}               # and a file no glob places takes its roles' layer.
targets:                      # outbound calls made from these files talk to this service
  "internal/adapters/out/billing/**": billing
dispatch:                     # the organization's own bus → the handlers of the message's type (core/dispatch.py;
  - calls: [Dispatch]         # MediatR is built in). `bus.Dispatch(new CreateOrder(..))` → `Execute` of `IHandles<CreateOrder>`
    handlers: [IHandles]
    method: Execute
entry_points:                 # symbols whose signature contains one of these are entry points
  signature_contains: ["*fiber.Ctx"]
  members_of:                 # methods of types whose declaration contains one of these (C# base lists)
    signature_contains: ["ICommandHandler<", "IEventHandler<"]
    names: ["Handle"]         # optional: only these methods
  roles: {use-case: [Execute]}   # methods of types with a role ([] = every method)
rules:
  - id: domain-is-pure        # File in layer `from` importing a File in one of `to` (an import of a
                              # namespace counts when every file declaring it is in one layer)
    forbid_import: {from: domain, to: [application, adapters-in, adapters-out]}
    severity: error
  - id: routes-in-adapters-in # HttpEndpoint declared outside these layers
    endpoints_only_in: [adapters-in]
    severity: warning
  - id: clients-in-adapters-out
    http_calls_only_in: [adapters-out]
    severity: warning
  - id: use-cases-in-application   # a type with this role in a file the layout places elsewhere
    roles_in: {use-case: [application]}
    severity: warning
```
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ..core.config import ConfigError
from ..core.dispatch import DispatchRule
from ..core.model import FileInfo, HttpCallInfo, ModuleInfo, SymbolInfo, ViolationInfo
from ..core.resolve import TYPE_KINDS
from ..core.scan_patterns import ScanPatterns
from . import layout, roles, rules
from .base import Convention, ConventionContext
from .declarations import Declarations

RULE_KINDS = ("forbid_import", "endpoints_only_in", "http_calls_only_in", "roles_in")


class DeclarativeConvention(Convention):
    def __init__(self, path: Path):
        self.path = path
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"{path}: invalid YAML: {e}")
        self.id = str(raw.get("id") or path.parent.name)
        self.layers = layout.layers(raw.get("layers"))
        self.architectures: list[layout.Architecture] = [
            (str(name), (a or {}).get("detect") or None, layout.layers((a or {}).get("layers")))
            for name, a in (raw.get("architectures") or {}).items()
        ]
        self.roles: roles.Roles = []
        for name, r in (raw.get("roles") or {}).items():
            r = r or {}
            if not any(k in r for k in ("extends", "name", "declares")):
                raise ConfigError(f"{path}: role '{name}' needs one of extends / name / declares")
            self.roles.append((str(name), r))
        self.role_layer = {name: r["layer"] for name, r in self.roles if r.get("layer")}
        self.targets: list[tuple[re.Pattern, str]] = [(layout.glob_re(g), str(svc)) for g, svc in (raw.get("targets") or {}).items()]
        self.patterns = ScanPatterns.from_dict(raw)
        if not isinstance(raw.get("dispatch") or [], list):
            raise ConfigError(f"{path}: dispatch must be a list of {{calls, handlers, method}}")
        self.dispatch_rules = [DispatchRule.from_dict(d, f"{path}: dispatch #{i + 1}")
                               for i, d in enumerate(raw.get("dispatch") or [])]
        ep = raw.get("entry_points") or {}
        self.entry_sig: tuple[str, ...] = tuple(ep.get("signature_contains") or [])
        members = ep.get("members_of") or {}
        self.owner_sig: tuple[str, ...] = tuple(members.get("signature_contains") or [])
        self.owner_methods: frozenset[str] = frozenset(members.get("names") or [])
        self.entry_roles: dict[str, frozenset[str]] = {str(k): frozenset(v or []) for k, v in (ep.get("roles") or {}).items()}
        self.rules: list[dict[str, Any]] = list(raw.get("rules") or [])
        for i, r in enumerate(self.rules):
            if not isinstance(r, dict) or not any(k in r for k in RULE_KINDS):
                raise ConfigError(f"{path}: rule #{i + 1} must have one of {' / '.join(RULE_KINDS)}")
            r.setdefault("id", f"rule{i + 1}")
            r.setdefault("severity", "warning")
        names = [a[0] for a in self.architectures]
        self.forced: str | None = None
        self.architecture: str | None = None
        self._arch_layers: layout.Layers = []
        self._role: dict[str, str] = {}                 # symbol id -> role
        self._file_roles: dict[str, set[str]] = {}      # file id -> roles of the types it declares
        self._path_layer: dict[str, str] = {}           # file id -> layer placed by a glob (not by roles)
        self._arch_names = names

    def configure(self, options: dict[str, Any]) -> None:
        arch = options.get("architecture")
        if arch is not None and str(arch) not in self._arch_names:
            raise ConfigError(f"{self.path}: architecture '{arch}' not declared (have: {', '.join(self._arch_names) or 'none'})")
        self.forced = str(arch) if arch is not None else None

    def scan_patterns(self) -> ScanPatterns:
        return self.patterns

    def dispatch(self) -> list[DispatchRule]:
        return self.dispatch_rules

    def describe(self) -> str:
        return f"{self.id}[{self.architecture}]" if self.architecture else self.id

    # ---- whole-repo view: layout and roles
    def prepare(self, ctx: ConventionContext) -> None:
        self.architecture, self._arch_layers = layout.select(self.architectures, self.forced, ctx.res.modules)
        self._role, self._file_roles, self._path_layer = {}, {}, {}
        if not self.roles:
            return
        types = [s for s in ctx.res.symbols if s.kind in TYPE_KINDS]
        declarations = Declarations(Path(ctx.res.repo.root), ctx.files_by_id, types)
        self._role, self._file_roles = roles.assign(types, self.roles, declarations)

    # ---- annotation
    def role_of(self, symbol: SymbolInfo, file: FileInfo) -> str | None:
        return self._role.get(symbol.id)

    def layer_of(self, file: FileInfo, module: ModuleInfo | None) -> str | None:
        for layer, rx in self._arch_layers + self.layers:
            if rx.match(file.path):
                self._path_layer[file.id] = layer
                return layer
        by_role = {self.role_layer.get(r) for r in self._file_roles.get(file.id, ())}
        if len(by_role) == 1:                   # unplaced by the layout: the roles it declares agree on one layer
            return next(iter(by_role))
        return None

    def target_of(self, call: HttpCallInfo, file: FileInfo) -> str | None:
        for rx, svc in self.targets:
            if rx.match(file.path):
                return svc
        return None

    def is_entry_point(self, symbol: SymbolInfo, file: FileInfo, owner: SymbolInfo | None = None) -> bool | None:
        if self.entry_sig and any(h in symbol.signature for h in self.entry_sig):
            return True
        if (self.owner_sig and owner is not None and symbol.kind == "method"
                and (not self.owner_methods or symbol.name in self.owner_methods)
                and any(h in owner.signature for h in self.owner_sig)):
            return True
        if owner is not None and symbol.kind == "method" and owner.role in self.entry_roles:
            methods = self.entry_roles[owner.role]
            if not methods or symbol.name in methods:
                return True
        return None

    # ---- rules
    def check(self, ctx: ConventionContext) -> list[ViolationInfo]:
        return rules.violations(self.id, self.rules, ctx, self._path_layer)
