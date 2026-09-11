"""`atlas.yaml` — what to index, from where, which refs (docs/indexing-process.md §3).

Location: $AIDD_CONFIG (default /app/atlas.yaml in the container, ~/.aidd/atlas.yaml on
the host, written by setup/install.sh). Nothing here has an implicit tenant: the file
must declare the tenant(s) explicitly.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import ConfigError

DEFAULT_CONFIG = "/app/atlas.yaml"


@dataclass
class ActivePolicy:
    max_age_days: int = 14
    max_per_repo: int = 5
    exclude: list[str] = field(default_factory=lambda: ["dependabot/*", "renovate/*", "docs/*", "ci/*", "cd/*", "pipeline/*"])


@dataclass
class RefPolicy:
    always: list[str] = field(default_factory=lambda: ["main", "master", "develop"])
    patterns: list[str] = field(default_factory=list)
    active: ActivePolicy = field(default_factory=ActivePolicy)
    gc_ephemeral_after_days: int = 30


@dataclass
class Source:
    type: str                       # local | github | gitlab | azure-devops | bitbucket
    path: str = ""                  # local
    org: str = ""                   # remote
    token_env: str = ""             # remote: NAME of the env var holding the token
    include: list[str] = field(default_factory=lambda: ["*"])
    exclude: list[str] = field(default_factory=list)
    skip_archived: bool = True
    fetch: bool = True              # local: run `git fetch --all --prune` before reading refs

    def selects(self, name: str) -> bool:
        return any(fnmatch.fnmatch(name, g) for g in self.include) and not any(fnmatch.fnmatch(name, g) for g in self.exclude)


@dataclass
class TenantConfig:
    name: str
    sources: list[Source]
    refs: RefPolicy
    areas: dict[str, list[str]] = field(default_factory=dict)   # optional: area -> repo names/globs
    schedule: str = ""

    def area_of(self, repo: str) -> str | None:
        for area, repos in self.areas.items():
            if any(fnmatch.fnmatch(repo, g) for g in repos):
                return area
        return None


@dataclass
class Manifest:
    path: Path
    tenants: dict[str, TenantConfig]

    def tenant(self, name: str | None) -> TenantConfig:
        if name:
            if name not in self.tenants:
                raise ConfigError(f"tenant '{name}' is not declared in {self.path} (declared: {', '.join(self.tenants) or 'none'})")
            return self.tenants[name]
        if len(self.tenants) == 1:
            return next(iter(self.tenants.values()))
        raise ConfigError(f"{self.path} declares {len(self.tenants)} tenants — pass --tenant")


def _expand(value: str) -> str:
    return os.path.expandvars(value) if isinstance(value, str) else value


def load_manifest(path: str | None = None) -> Manifest:
    p = Path(path or os.getenv("AIDD_CONFIG", DEFAULT_CONFIG))
    if p.is_dir():
        raise ConfigError(
            f"{p} is a directory, not a file. Docker creates a directory when a bind-mounted file is missing: "
            "~/.aidd/atlas.yaml did not exist when the container was created. "
            "Fix on the host: cd ~/.aidd && docker compose down && rmdir atlas.yaml && ./setup/install.sh (or write atlas.yaml by hand)")
    if not p.exists():
        raise ConfigError(f"manifest not found at {p} — setup/install.sh writes it; or pass --config")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML in {p}: {e}")

    tenants_raw = raw.get("tenants")
    if not isinstance(tenants_raw, dict) or not tenants_raw:
        raise ConfigError(f"{p}: 'tenants' must be a non-empty mapping")

    tenants: dict[str, TenantConfig] = {}
    for name, t in tenants_raw.items():
        t = t or {}
        sources = []
        for s in t.get("sources") or []:
            if "type" not in s:
                raise ConfigError(f"{p}: tenant '{name}': every source needs a 'type'")
            sources.append(Source(
                type=s["type"], path=_expand(s.get("path", "")), org=s.get("org", ""),
                token_env=s.get("token_env", ""), include=s.get("include") or ["*"],
                exclude=s.get("exclude") or [], skip_archived=bool(s.get("skip_archived", True)),
                fetch=bool(s.get("fetch", True)),
            ))
        if not sources:
            raise ConfigError(f"{p}: tenant '{name}' has no sources")
        for s in sources:
            if s.type == "local" and not s.path:
                raise ConfigError(f"{p}: tenant '{name}': local source needs 'path'")
            if s.type != "local" and (not s.org or not s.token_env):
                raise ConfigError(f"{p}: tenant '{name}': {s.type} source needs 'org' and 'token_env'")

        r = t.get("refs") or {}
        a = r.get("active") or {}
        refs = RefPolicy(
            always=r.get("always", RefPolicy().always),
            patterns=r.get("patterns") or [],
            active=ActivePolicy(
                max_age_days=int(a.get("max_age_days", 14)),
                max_per_repo=int(a.get("max_per_repo", 5)),
                exclude=a.get("exclude", ActivePolicy().exclude),
            ),
            gc_ephemeral_after_days=int(r.get("gc_ephemeral_after_days", 30)),
        )
        areas = {k: list(v or []) for k, v in (t.get("areas") or {}).items()}
        tenants[name] = TenantConfig(name=name, sources=sources, refs=refs, areas=areas, schedule=t.get("schedule", "") or "")
    return Manifest(path=p, tenants=tenants)
