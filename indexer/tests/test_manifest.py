"""F0.3.6: per-repo ref policy (`refs.overrides`) on top of the tenant defaults."""
from __future__ import annotations

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
