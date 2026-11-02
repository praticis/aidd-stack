"""`atlas.yaml` as `load_manifest` reads it: what each tenant gets, the per-repo ref policy (`refs.overrides`) on top of
the tenant defaults, and what it refuses."""
from __future__ import annotations

from dataclasses import asdict

import pytest

from aidd_indexer.core.config import ConfigError
from aidd_indexer.core.manifest import load_manifest

YAML = """
tenants:
  acme:
    sources:
      - type: local
        path: /workspace/acme
    refs:
      always: ["main", "develop"]
      active: {max_age_days: 14, max_per_repo: 5}
      overrides:
        project-a:
          always: ["main"]
        "legacy-*":
          always: ["master"]
          patterns: ["release/*"]
          active: false
"""


def test_overrides_apply_per_repo(tmp_path):
    f = tmp_path / "atlas.yaml"
    f.write_text(YAML, encoding="utf-8")
    refs = load_manifest(str(f)).tenant("acme").refs
    assert refs.for_repo("project-b").always == ["main", "develop"]          # tenant default
    assert refs.for_repo("project-a").always == ["main"]                     # exact name
    legacy = refs.for_repo("legacy-billing")                                 # glob
    assert legacy.always == ["master"] and legacy.patterns == ["release/*"]
    assert legacy.active.max_per_repo == 0                                   # active: false
    assert refs.for_repo("project-a").active.max_age_days == 14              # untouched fields inherited
    assert refs.always == ["main", "develop"]                                # defaults not mutated


def test_overrides_must_be_a_map(tmp_path):
    f = tmp_path / "atlas.yaml"
    f.write_text(YAML.replace("overrides:\n        project-a:\n          always: [\"main\"]\n        \"legacy-*\":\n          always: [\"master\"]\n          patterns: [\"release/*\"]\n          active: false", "overrides: [project-a]"), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_manifest(str(f))


def _load(tmp_path, text: str):
    f = tmp_path / "atlas.yaml"
    f.write_text(text, encoding="utf-8")
    return f, lambda: load_manifest(str(f))


def _refused(tmp_path, text: str) -> tuple[str, str]:
    f, load = _load(tmp_path, text)
    with pytest.raises(ConfigError) as e:
        load()
    return str(f), str(e.value)


LOCAL = "      - type: local\n        path: /workspace/acme\n"


@pytest.mark.parametrize("text,message", [
    ("tenants: {}\n", "'tenants' must be a non-empty mapping"),
    ("tenants: [acme]\n", "'tenants' must be a non-empty mapping"),
    ("other: 1\n", "'tenants' must be a non-empty mapping"),
    ("", "'tenants' must be a non-empty mapping"),
    ("tenants:\n  acme:\n    sources:\n      - path: /x\n", "tenant 'acme': every source needs a 'type'"),
    ("tenants:\n  acme:\n    sources: []\n", "tenant 'acme' has no sources"),
    ("tenants:\n  acme:\n", "tenant 'acme' has no sources"),
    ("tenants:\n  acme:\n    sources:\n      - type: local\n", "tenant 'acme': local source needs 'path'"),
    ("tenants:\n  acme:\n    sources:\n      - type: github\n        org: acme\n",
     "tenant 'acme': github source needs 'org' and 'token_env'"),
    ("tenants:\n  acme:\n    sources:\n      - type: gitlab\n        token_env: T\n",
     "tenant 'acme': gitlab source needs 'org' and 'token_env'"),
    (f"tenants:\n  acme:\n    sources:\n{LOCAL}    refs:\n      overrides: [x]\n",
     "tenant 'acme': 'refs.overrides' must be a map of repo name/glob -> policy"),
    (f"tenants:\n  acme:\n    sources:\n{LOCAL}    conventions: dotnet-praticis\n",
     "tenant 'acme': 'conventions' must be a list"),
    # with two defects, the one met first wins: every source is built before any is checked, then refs, then conventions
    ("tenants:\n  acme:\n    sources:\n      - type: local\n      - path: /x\n", "tenant 'acme': every source needs a 'type'"),
    ("tenants:\n  acme:\n    sources:\n      - type: local\n    refs:\n      overrides: [x]\n",
     "tenant 'acme': local source needs 'path'"),
    (f"tenants:\n  acme:\n    sources:\n{LOCAL}    refs:\n      overrides: [x]\n    conventions: x\n",
     "tenant 'acme': 'refs.overrides' must be a map"),
    (f"tenants:\n  acme:\n    sources:\n{LOCAL}    conventions: x\n  beta:\n    sources: []\n",
     "tenant 'acme': 'conventions' must be a list"),
])
def test_each_refusal_names_the_file_and_the_tenant(tmp_path, text, message):
    path, said = _refused(tmp_path, text)
    assert said.startswith(f"{path}: {message}")


def test_a_missing_file_a_directory_and_bad_yaml(tmp_path):
    with pytest.raises(ConfigError) as e:
        load_manifest(str(tmp_path / "none.yaml"))
    assert str(e.value) == f"manifest not found at {tmp_path / 'none.yaml'} — setup/install.sh writes it; or pass --config"
    with pytest.raises(ConfigError) as e:
        load_manifest(str(tmp_path))
    assert str(e.value) == (
        f"{tmp_path} is a directory, not a file. Docker creates a directory when a bind-mounted file is missing: "
        "~/.aidd/atlas.yaml did not exist when the container was created. "
        "Fix on the host: cd ~/.aidd && docker compose down && rmdir atlas.yaml && ./setup/install.sh (or write atlas.yaml by hand)")
    path, said = _refused(tmp_path, "tenants: [\n")
    assert said.startswith(f"invalid YAML in {path}: ") and said != f"invalid YAML in {path}: "


def test_what_a_tenant_gets_by_default_and_as_declared(tmp_path, monkeypatch):
    monkeypatch.setenv("WS", "/workspace")
    _, load = _load(tmp_path, """
tenants:
  acme:
    sources:
      - type: local
        path: ${WS}/acme
        include: []
    schedule: null
    areas: {payments: ["pay-*"], empty: null}
    conventions: [{id: dotnet-praticis, path: "${WS}/conv"}, "${WS}/c2"]
    refs:
      overrides: {good: {always: [main]}, dropped: [x]}
  beta:
    sources:
      - {type: github, org: beta, token_env: BETA_TOKEN, exclude: [old-*], skip_archived: false, fetch: false}
    schedule: "*/30 * * * *"
    refs:
      always: []
      patterns: [release/*]
      active: {max_age_days: 7, max_per_repo: 2, exclude: []}
      gc_ephemeral_after_days: 10
""")
    m = load()
    assert list(m.tenants) == ["acme", "beta"]
    assert asdict(m.tenants["acme"]) == {
        "name": "acme",
        "sources": [{"type": "local", "path": "/workspace/acme", "org": "", "token_env": "", "include": ["*"],
                     "exclude": [], "skip_archived": True, "fetch": True}],
        "refs": {"always": ["main", "master", "develop"], "patterns": [],
                 "active": {"max_age_days": 14, "max_per_repo": 5,
                            "exclude": ["dependabot/*", "renovate/*", "docs/*", "ci/*", "cd/*", "pipeline/*"]},
                 "gc_ephemeral_after_days": 30, "overrides": {"good": {"always": ["main"]}}},
        "areas": {"payments": ["pay-*"], "empty": []}, "schedule": "",
        "conventions": [{"id": "dotnet-praticis", "path": "/workspace/conv"}, "/workspace/c2"]}
    assert asdict(m.tenants["beta"]) == {
        "name": "beta",
        "sources": [{"type": "github", "path": "", "org": "beta", "token_env": "BETA_TOKEN", "include": ["*"],
                     "exclude": ["old-*"], "skip_archived": False, "fetch": False}],
        "refs": {"always": [], "patterns": ["release/*"], "active": {"max_age_days": 7, "max_per_repo": 2, "exclude": []},
                 "gc_ephemeral_after_days": 10, "overrides": {}},
        "areas": {}, "schedule": "*/30 * * * *", "conventions": []}
