"""policy.yaml: layers, origins, validation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aidd_indexer.core.config import ConfigError
from aidd_indexer.core.policy import BUILTIN, BUILTIN_TOPICS, load_policy

EXAMPLE = Path(__file__).parent.parent / "policy.example.yaml"

POLICY = """
version: 1
defaults:
  coverage: {min: 75}
tenants:
  acme:
    coverage: {new_code_min: 85}
    knowledge: {topics: [performance]}
    areas:
      payments:
        coverage: {min: 90}
    overrides:
      legacy-*:
        coverage: {min: 40}
      legacy-billing:
        harness: {max_attempts: 5}
"""


def _write(tmp_path: Path, text: str) -> str:
    p = tmp_path / "policy.yaml"
    p.write_text(text)
    return str(p)


def test_no_file_means_built_in_defaults(tmp_path: Path):
    pol = load_policy(str(tmp_path / "missing.yaml"))
    eff = pol.effective("acme", "orders-api")
    assert pol.path is None and eff.get("coverage.min") == BUILTIN["coverage"]["min"]
    assert set(eff.origin.values()) == {"built-in"}
    assert eff.get("knowledge.topics") == list(BUILTIN_TOPICS)


def test_layers_and_origins(tmp_path: Path):
    pol = load_policy(_write(tmp_path, POLICY))
    eff = pol.effective("acme", "orders-api", area=None)
    assert eff.get("coverage.min") == 75 and eff.origin["coverage.min"] == "defaults"
    assert eff.get("coverage.new_code_min") == 85 and eff.origin["coverage.new_code_min"] == "tenant acme"
    assert eff.get("harness.max_attempts") == 3 and eff.origin["harness.max_attempts"] == "built-in"
    assert eff.get("knowledge.topics") == list(BUILTIN_TOPICS) + ["performance"]       # topics add, never remove

    pay = pol.effective("acme", "card-api", area="payments")
    assert pay.get("coverage.min") == 90 and pay.origin["coverage.min"] == "area payments"

    legacy = pol.effective("acme", "legacy-billing", area="payments")
    assert legacy.get("coverage.min") == 40 and legacy.origin["coverage.min"] == "override 'legacy-*'"   # repo beats area
    assert legacy.get("harness.max_attempts") == 5 and legacy.origin["harness.max_attempts"] == "override 'legacy-billing'"


def test_a_tenant_without_policy_gets_the_defaults(tmp_path: Path):
    eff = load_policy(_write(tmp_path, POLICY)).effective("globex", "x")
    assert eff.get("coverage.min") == 75 and eff.get("coverage.new_code_min") == 80


def test_effective_values_are_copies(tmp_path: Path):
    pol = load_policy(_write(tmp_path, POLICY))
    pol.effective("acme").values["review"]["adr_when"].append("x")
    assert BUILTIN["review"]["adr_when"] == ["new-integration", "new-module"]


@pytest.mark.parametrize("text,message", [
    ("defaults:\n  coverage: {minimum: 70}\n", "unknown key 'minimum' — did you mean 'min'?"),
    ("defaults:\n  coverag: {min: 70}\n", "did you mean 'coverage'?"),
    ("defaults:\n  coverage: {min: 170}\n", "coverage.min: must be a number between 0 and 100"),
    ("defaults:\n  harness: {max_attempts: 2.5}\n", "must be an integer between 1 and 20"),
    ("defaults:\n  review: {spec_approval: maybe}\n", "must be one of required, optional"),
    ("defaults:\n  review: {adr_when: [new-thing]}\n", "a list of ADR triggers"),
    ("defaults:\n  knowledge: {topics: [Perf Stuff]}\n", "lowercase topic slugs"),
    ("defaults:\n  knowledge: {language: Portuguese}\n", "a language tag"),
    ("tenants:\n  acme:\n    overrides: [x]\n", "overrides: must be a mapping"),
    ("tenants:\n  acme:\n    areas:\n      payments:\n        coverage: {min: -1}\n", "tenants.acme.areas.payments.coverage.min"),
    ("version: 2\n", "version 2 is not supported"),
    ("defualts: {}\n", "did you mean 'defaults'?"),
])
def test_validation_names_the_problem(tmp_path: Path, text: str, message: str):
    with pytest.raises(ConfigError) as e:
        load_policy(_write(tmp_path, text))
    assert message in str(e.value)


def test_a_directory_is_explained(tmp_path: Path):
    d = tmp_path / "policy.yaml"
    d.mkdir()
    with pytest.raises(ConfigError, match="rmdir policy.yaml"):
        load_policy(str(d))


def test_the_shipped_example_is_valid_and_equals_the_built_ins():
    eff = load_policy(str(EXAMPLE)).effective("acme", "x")
    assert eff.values == load_policy("/nonexistent").effective("acme", "x").values


def test_cli_show_json(tmp_path: Path, capsys, monkeypatch):
    from aidd_indexer.cli import main
    monkeypatch.delenv("AIDD_TENANT", raising=False)
    manifest = tmp_path / "atlas.yaml"
    manifest.write_text(f"tenants:\n  acme:\n    sources:\n      - type: local\n        path: {tmp_path}\n"
                        "    areas:\n      payments: [card-*]\n")
    rc = main(["policy", "show", "card-api", "--policy", _write(tmp_path, POLICY), "--config", str(manifest), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["tenant"] == "acme" and out["area"] == "payments"
    assert out["policy"]["coverage"]["min"] == 90 and out["origin"]["coverage.min"] == "area payments"
    assert main(["policy", "check", "--policy", str(tmp_path / "policy.yaml")]) == 0
