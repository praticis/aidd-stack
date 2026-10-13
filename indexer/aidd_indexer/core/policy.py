"""`policy.yaml` — what the development process requires (coverage, harness, review, knowledge).

`atlas.yaml` says how to read the code; this file says what the process demands of it. Location:
$AIDD_POLICY (default /app/policy.yaml in the container, ~/.aidd/policy.yaml on the host, written by
setup/install.sh). The file is optional: without it every value is the built-in default.

Layers, each overriding only the keys it declares (later wins):

    built-in  →  defaults  →  tenants.<t>  →  tenants.<t>.areas.<area>  →  tenants.<t>.overrides.<repo|glob>

Areas come from `atlas.yaml` (`areas:`); overrides match repo names with globs, in declaration order.
Skills never merge the layers themselves: they read the effective policy (`aidd policy show`, and the
`policy_for` tool of the knowledge service), which also says where each value came from.
"""

from __future__ import annotations

import copy
import difflib
import fnmatch
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from .config import ConfigError

DEFAULT_POLICY = "/app/policy.yaml"

# the topic vocabulary of insights (docs/knowledge-contract.md); `knowledge.topics` adds to it
BUILTIN_TOPICS = ("architecture", "review", "quality", "security", "incident", "decision", "business")
ADR_TRIGGERS = ("new-integration", "new-module", "new-dependency", "contract-change", "data-migration")

BUILTIN: dict[str, Any] = {
    "coverage": {"min": 70, "new_code_min": 80},
    "harness": {"max_attempts": 3},
    "review": {"spec_approval": "required", "adr_when": ["new-integration", "new-module"]},
    "knowledge": {"recurring_after": 3, "archive_after_days": 180, "topics": []},
}

_SLUG = re.compile(r"^[a-z][a-z0-9-]*$")


def _number(lo: float, hi: float) -> Callable[[Any], str | None]:
    def check(v: Any) -> str | None:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            return f"a number between {lo:g} and {hi:g}"
        return None
    return check


def _integer(lo: int, hi: int) -> Callable[[Any], str | None]:
    def check(v: Any) -> str | None:
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            return f"an integer between {lo} and {hi}"
        return None
    return check


def _one_of(*allowed: str) -> Callable[[Any], str | None]:
    def check(v: Any) -> str | None:
        return None if v in allowed else f"one of {', '.join(allowed)}"
    return check


def _list_of(item: Callable[[Any], str | None], what: str) -> Callable[[Any], str | None]:
    def check(v: Any) -> str | None:
        if not isinstance(v, list) or any(item(x) for x in v):
            return f"a list of {what}"
        return None
    return check


def _slug(v: Any) -> str | None:
    return None if isinstance(v, str) and _SLUG.match(v) else "a lowercase slug"


SPEC: dict[str, dict[str, Callable[[Any], str | None]]] = {
    "coverage": {"min": _number(0, 100), "new_code_min": _number(0, 100)},
    "harness": {"max_attempts": _integer(1, 20)},
    "review": {"spec_approval": _one_of("required", "optional"),
               "adr_when": _list_of(_one_of(*ADR_TRIGGERS), f"ADR triggers ({', '.join(ADR_TRIGGERS)})")},
    "knowledge": {"recurring_after": _integer(2, 100), "archive_after_days": _integer(1, 3650),
                  "topics": _list_of(_slug, "lowercase topic slugs")},
}


def _unknown(where: str, key: str, known: list[str]) -> ConfigError:
    near = difflib.get_close_matches(key, known, n=1)
    hint = f" — did you mean '{near[0]}'?" if near else f" (known: {', '.join(known)})"
    return ConfigError(f"{where}: unknown key '{key}'{hint}")


def _validate_layer(where: str, layer: Any, extra: tuple[str, ...] = ()) -> dict[str, Any]:
    """Check one layer against SPEC; `extra` are structural keys allowed at that level (areas, overrides)."""
    if layer is None:
        return {}
    if not isinstance(layer, dict):
        raise ConfigError(f"{where}: must be a mapping")
    for section, values in layer.items():
        if section in extra:
            continue
        if section not in SPEC:
            raise _unknown(where, section, list(SPEC) + list(extra))
        if not isinstance(values, dict):
            raise ConfigError(f"{where}.{section}: must be a mapping")
        for key, value in values.items():
            if key not in SPEC[section]:
                raise _unknown(f"{where}.{section}", key, list(SPEC[section]))
            problem = SPEC[section][key](value)
            if problem:
                raise ConfigError(f"{where}.{section}.{key}: must be {problem} (got {value!r})")
    return layer


@dataclass
class TenantPolicy:
    base: dict[str, Any] = field(default_factory=dict)
    areas: dict[str, dict[str, Any]] = field(default_factory=dict)
    overrides: list[tuple[str, dict[str, Any]]] = field(default_factory=list)   # (repo glob, layer), file order


@dataclass
class Policy:
    path: Path | None                   # None: no file, built-in defaults only
    defaults: dict[str, Any] = field(default_factory=dict)
    tenants: dict[str, TenantPolicy] = field(default_factory=dict)

    def effective(self, tenant: str | None = None, repo: str | None = None,
                  area: str | None = None) -> "Effective":
        layers: list[tuple[str, dict[str, Any]]] = [("built-in", BUILTIN), ("defaults", self.defaults)]
        t = self.tenants.get(tenant or "")
        if t is not None:
            layers.append((f"tenant {tenant}", t.base))
            if area and area in t.areas:
                layers.append((f"area {area}", t.areas[area]))
            if repo:
                layers += [(f"override '{glob}'", layer) for glob, layer in t.overrides if fnmatch.fnmatch(repo, glob)]
        values: dict[str, Any] = {}
        origin: dict[str, str] = {}
        for label, layer in layers:
            for section, keys in layer.items():
                for key, value in keys.items():
                    values.setdefault(section, {})[key] = copy.deepcopy(value)
                    origin[f"{section}.{key}"] = label
        topics = list(BUILTIN_TOPICS) + [x for x in values["knowledge"]["topics"] if x not in BUILTIN_TOPICS]
        values["knowledge"]["topics"] = topics
        return Effective(tenant=tenant, repo=repo, area=area, values=values, origin=origin, path=self.path)


@dataclass
class Effective:
    tenant: str | None
    repo: str | None
    area: str | None
    values: dict[str, Any]
    origin: dict[str, str]              # "section.key" -> layer label
    path: Path | None

    def get(self, dotted: str) -> Any:
        section, key = dotted.split(".", 1)
        return self.values[section][key]

    def as_dict(self) -> dict[str, Any]:
        return {"tenant": self.tenant, "repo": self.repo, "area": self.area,
                "source": str(self.path) if self.path else None, "policy": self.values, "origin": self.origin}


def load_policy(path: str | None = None) -> Policy:
    p = Path(path or os.getenv("AIDD_POLICY", DEFAULT_POLICY))
    if p.is_dir():
        raise ConfigError(
            f"{p} is a directory, not a file. Docker creates a directory when a bind-mounted file is missing: "
            "~/.aidd/policy.yaml did not exist when the container was created. "
            "Fix on the host: cd ~/.aidd && docker compose down && rmdir policy.yaml && ./setup/install.sh")
    if not p.exists():
        return Policy(path=None)
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML in {p}: {e}")
    if not isinstance(raw, dict):
        raise ConfigError(f"{p}: must be a mapping (version, defaults, tenants)")
    for key in raw:
        if key not in ("version", "defaults", "tenants"):
            raise _unknown(str(p), key, ["version", "defaults", "tenants"])
    if raw.get("version", 1) != 1:
        raise ConfigError(f"{p}: version {raw['version']!r} is not supported by this indexer (expected 1)")

    policy = Policy(path=p, defaults=_validate_layer(f"{p}: defaults", raw.get("defaults")))
    tenants = raw.get("tenants") or {}
    if not isinstance(tenants, dict):
        raise ConfigError(f"{p}: 'tenants' must be a mapping of tenant -> policy")
    for name, t in tenants.items():
        where = f"{p}: tenants.{name}"
        t = _validate_layer(where, t, extra=("areas", "overrides"))
        tp = TenantPolicy(base={k: v for k, v in t.items() if k not in ("areas", "overrides")})
        for kind in ("areas", "overrides"):
            group = t.get(kind) or {}
            if not isinstance(group, dict):
                raise ConfigError(f"{where}.{kind}: must be a mapping of {'area' if kind == 'areas' else 'repo name/glob'} -> policy")
            for key, layer in group.items():
                layer = _validate_layer(f"{where}.{kind}.{key}", layer)
                if kind == "areas":
                    tp.areas[str(key)] = layer
                else:
                    tp.overrides.append((str(key), layer))
        policy.tenants[str(name)] = tp
    return policy
