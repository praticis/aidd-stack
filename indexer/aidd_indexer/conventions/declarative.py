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

import fnmatch
import re
from pathlib import Path
from typing import Any

import yaml

from ..core import ids
from ..core.config import ConfigError
from ..core.extract import strip_attributes
from ..core.model import FileInfo, HttpCallInfo, ModuleInfo, SymbolInfo, ViolationInfo
from ..core.scan_patterns import ScanPatterns
from .base import Convention, ConventionContext

RULE_KINDS = ("forbid_import", "endpoints_only_in", "http_calls_only_in", "roles_in")
TYPE_KINDS = frozenset({"class", "interface", "struct", "record", "type"})


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


def _layers(spec: dict | None) -> list[tuple[str, re.Pattern]]:
    return [(layer, _glob_re(g)) for layer, globs in (spec or {}).items() for g in (globs or [])]


def _split_top(text: str) -> list[str]:
    """Split on commas outside (), <>, []."""
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    return parts + [cur]


def base_names(header: str) -> list[str]:
    """Simple names in a type declaration's base list: C# `class X(..) : A<T>, B where T : C`,
    TS/Java `class X extends A implements B, C`, Python `class X(A, B):`."""
    h = strip_attributes(header.split("{", 1)[0])
    m = re.search(r"\b(?:extends|implements)\b(.*)", h)
    if m:
        text = re.sub(r"\b(?:extends|implements)\b", ",", m.group(1))
    else:
        depth, idx = 0, None
        for i, ch in enumerate(h):
            if ch in "(<[":
                depth += 1
            elif ch in ")>]":
                depth -= 1
            elif ch == ":" and depth == 0:
                idx = i
                break
        if idx is None:
            return []
        text = h[idx + 1:]
        if not text.strip():                                               # Python: `class X(A, B):`
            pm = re.search(r"\bclass\s+\w+\s*\((.*)\)\s*$", h[:idx])
            text = pm.group(1) if pm else ""
        text = re.split(r"\bwhere\b", text)[0]
    out = []
    for part in _split_top(text):
        name = re.sub(r"[<(].*$", "", part.strip()).strip().rstrip("?").split(".")[-1]
        if re.fullmatch(r"[A-Za-z_]\w*", name) and "=" not in part:
            out.append(name)
    return out


def _detected(detect: dict[str, Any], modules: list[str]) -> bool:
    """`modules`: any module path matches one of the globs. `together`: module names (last path
    segment) that must all exist for the same `{placeholder}` value — `["{svc}.Api", "{svc}.Core"]`
    is one service's two projects, not an unrelated `Shared.Bus.Core` library next to an `.Api`."""
    if detect.get("modules") and not any(_glob_re(g).match(p) for g in detect["modules"] for p in modules):
        return False
    together = detect.get("together") or []
    if together:
        names = [p.rsplit("/", 1)[-1] for p in modules]
        bindings: set[tuple[str, ...]] | None = None
        for pat in together:
            keys = re.findall(r"\{(\w+)\}", pat)
            rx = re.compile("^" + re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>.+)", re.escape(pat)) + "$")
            found = {tuple(m.group(k) for k in keys) for n in names if (m := rx.match(n))}
            bindings = found if bindings is None else bindings & found
            if not bindings:
                return False
    return bool(detect.get("modules") or together)


class DeclarativeConvention(Convention):
    def __init__(self, path: Path):
        self.path = path
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"{path}: invalid YAML: {e}")
        self.id = str(raw.get("id") or path.parent.name)
        self.layers = _layers(raw.get("layers"))
        self.architectures: list[tuple[str, dict[str, Any] | None, list[tuple[str, re.Pattern]]]] = [
            (str(name), (a or {}).get("detect") or None, _layers((a or {}).get("layers")))
            for name, a in (raw.get("architectures") or {}).items()
        ]
        self.roles: list[tuple[str, dict[str, Any]]] = []
        for name, r in (raw.get("roles") or {}).items():
            r = r or {}
            if not any(k in r for k in ("extends", "name", "declares")):
                raise ConfigError(f"{path}: role '{name}' needs one of extends / name / declares")
            self.roles.append((str(name), r))
        self.role_layer = {name: r["layer"] for name, r in self.roles if r.get("layer")}
        self.targets: list[tuple[re.Pattern, str]] = [(_glob_re(g), str(svc)) for g, svc in (raw.get("targets") or {}).items()]
        self.patterns = ScanPatterns.from_dict(raw)
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
        self._arch_layers: list[tuple[str, re.Pattern]] = []
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

    def describe(self) -> str:
        return f"{self.id}[{self.architecture}]" if self.architecture else self.id

    # ---- whole-repo view: layout and roles
    def prepare(self, ctx: ConventionContext) -> None:
        self.architecture, self._arch_layers = self._select(ctx)
        self._role, self._file_roles, self._path_layer = {}, {}, {}
        if not self.roles:
            return
        types = [s for s in ctx.res.symbols if s.kind in TYPE_KINDS]
        by_name: dict[str, list[SymbolInfo]] = {}
        for s in types:
            by_name.setdefault(s.name, []).append(s)
        root = Path(ctx.res.repo.root)
        sources: dict[str, list[str]] = {}

        def header(s: SymbolInfo) -> str:
            f = ctx.files_by_id.get(s.file_id)
            if f is None:
                return s.signature
            if f.id not in sources:
                try:
                    sources[f.id] = (root / f.path).read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    sources[f.id] = []
            lines = sources[f.id][s.line_start - 1: s.line_start + 14] or [s.signature]
            text = ""
            for ln in lines:                     # the declaration up to its body (base lists may span lines)
                text += " " + ln
                if "{" in ln or ln.rstrip().endswith(";"):
                    break
            return " ".join(text.split())

        bases: dict[str, list[str]] = {s.id: base_names(header(s)) for s in types}
        heads: dict[str, str] = {}

        def ancestors(s: SymbolInfo, seen: set[str]) -> set[str]:
            out: set[str] = set()
            for b in bases.get(s.id, []):
                out.add(b)
                for t in by_name.get(b, []):     # an in-repo base passes its own bases on
                    if t.id not in seen:
                        out |= ancestors(t, seen | {t.id})
            return out

        for s in types:
            anc = None
            for role, spec in self.roles:
                hit = False
                if spec.get("name") and any(fnmatch.fnmatchcase(s.name, g) for g in spec["name"]):
                    hit = True
                if not hit and spec.get("extends"):
                    anc = anc if anc is not None else ancestors(s, {s.id})
                    hit = any(n in anc for n in spec["extends"])
                if not hit and spec.get("declares"):
                    h = heads.setdefault(s.id, header(s))
                    hit = any(d in h for d in spec["declares"])
                if hit:
                    self._role[s.id] = role
                    self._file_roles.setdefault(s.file_id, set()).add(role)
                    break

    def _select(self, ctx: ConventionContext) -> tuple[str | None, list[tuple[str, re.Pattern]]]:
        if not self.architectures:
            return None, []
        if self.forced:
            return next((n, l) for n, _, l in self.architectures if n == self.forced)
        modules = [m.path for m in ctx.res.modules if m.path]
        for name, detect, layers in self.architectures:          # declared order among those with `detect`
            if detect is not None and _detected(detect, modules):
                return name, layers
        return next(((n, l) for n, d, l in self.architectures if d is None), (None, []))   # the default

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
        out: list[ViolationInfo] = []
        repo = ctx.res.repo
        files = ctx.files_by_id

        def emit(rule: dict, f: FileInfo, line: int, msg: str, symbol_id: str | None = None) -> None:
            out.append(ViolationInfo(
                id=ids.violation(repo.tenant, repo.name, repo.ref, self.id, rule["id"], f.path, line),
                convention=self.id, rule=rule["id"], severity=rule["severity"], message=msg,
                file_id=f.id, line=line, symbol_id=symbol_id, evidence=f"{repo.name}:{f.path}:{line}",
            ))

        def import_target(e) -> tuple[str | None, str] | None:
            """(layer, shown name) of what an import reaches: the File, or — for an import of a
            namespace, which targets its Module (C#) — the one layer of the files declaring it."""
            if e.target_label == "File":
                t = files.get(e.target_id)
                return (ctx.file_layer.get(t.id), t.path) if t is not None else None
            if e.target_label == "Module":
                layers = {ctx.file_layer.get(fid) for fid in ctx.rv.namespace_files.get(e.spec, ())}
                if len(layers) == 1:          # a namespace spread over layers says nothing about the dependency
                    return next(iter(layers)), e.spec
            return None

        for rule in self.rules:
            if "forbid_import" in rule:
                spec = rule["forbid_import"] or {}
                src_layer, to = spec.get("from"), set(spec.get("to") or [])
                for e in ctx.rv.imports:
                    f = files.get(e.file_id)
                    if f is None or ctx.file_layer.get(f.id) != src_layer:
                        continue
                    hit = import_target(e)
                    if hit is not None and hit[0] in to:
                        emit(rule, f, e.line, f"{src_layer} imports {hit[0]} ({hit[1]})")
            elif "endpoints_only_in" in rule:
                allowed = set(rule["endpoints_only_in"] or [])
                for ep in ctx.res.endpoints:
                    f = files.get(ep.file_id)
                    if f is not None and ctx.file_layer.get(f.id) not in allowed:
                        emit(rule, f, ep.line, f"{ep.method} {ep.path} declared in layer "
                             f"{ctx.file_layer.get(f.id) or '(none)'}, allowed: {', '.join(sorted(allowed))}", ep.handler_id)
            elif "roles_in" in rule:
                allowed_by_role = {str(k): set(v or []) for k, v in (rule["roles_in"] or {}).items()}
                for sym in ctx.res.symbols:
                    allowed = allowed_by_role.get(sym.role or "")
                    f = files.get(sym.file_id)
                    layer = self._path_layer.get(sym.file_id)      # only where the layout put it, not inferred from the role
                    if allowed is None or f is None or layer is None or layer in allowed:
                        continue
                    emit(rule, f, sym.line_start, f"{sym.role} {sym.name} lives in layer {layer}, "
                         f"expected: {', '.join(sorted(allowed))}", sym.id)
            elif "http_calls_only_in" in rule:
                allowed = set(rule["http_calls_only_in"] or [])
                for c in ctx.res.http_calls:
                    f = files.get(c.file_id)
                    if f is not None and ctx.file_layer.get(f.id) not in allowed:
                        emit(rule, f, c.line, f"outbound {c.method} {c.path} from layer "
                             f"{ctx.file_layer.get(f.id) or '(none)'}, allowed: {', '.join(sorted(allowed))}", c.caller_id)
        return out
