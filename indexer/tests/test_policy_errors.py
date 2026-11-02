"""What `load_policy` refuses, one section and one level at a time, each message whole, and which defect it names
when a file has two."""
from __future__ import annotations

from pathlib import Path

import pytest

from aidd_indexer.core.config import ConfigError
from aidd_indexer.core.policy import load_policy

ALL = "coverage, harness, review, knowledge"


def _refusal(tmp_path: Path, text: str) -> tuple[str, str]:
    p = tmp_path / "policy.yaml"
    p.write_text(text)
    with pytest.raises(ConfigError) as e:
        load_policy(str(p))
    return str(p), str(e.value)


@pytest.mark.parametrize("text,message", [
    ("- a\n", "{p}: must be a mapping (version, defaults, tenants)"),
    ("tenants: [acme]\n", "{p}: 'tenants' must be a mapping of tenant -> policy"),
    ("tenants:\n  acme: [x]\n", "{p}: tenants.acme: must be a mapping"),
    ("tenants:\n  acme:\n    areas: [x]\n", "{p}: tenants.acme.areas: must be a mapping of area -> policy"),
    ("tenants:\n  acme:\n    overrides: [x]\n", "{p}: tenants.acme.overrides: must be a mapping of repo name/glob -> policy"),
    ("tenants:\n  acme:\n    zzz: {}\n", f"{{p}}: tenants.acme: unknown key 'zzz' (known: {ALL}, areas, overrides)"),
    ("tenants:\n  acme:\n    areas:\n      payments: 5\n", "{p}: tenants.acme.areas.payments: must be a mapping"),
    ("tenants:\n  acme:\n    overrides:\n      legacy-*:\n        harness: {max_attempts: 0}\n",
     "{p}: tenants.acme.overrides.legacy-*.harness.max_attempts: must be an integer between 1 and 20 (got 0)"),
    ("defaults: 5\n", "{p}: defaults: must be a mapping"),
    ("defaults:\n  areas: {}\n", "{p}: defaults: unknown key 'areas' — did you mean 'harness'?"),
    ("defaults:\n  overrides: {}\n", f"{{p}}: defaults: unknown key 'overrides' (known: {ALL})"),
    ("version: 3\n", "{p}: version 3 is not supported by this indexer (expected 1)"),
    ("verison: 1\n", "{p}: unknown key 'verison' — did you mean 'version'?"),
    ("zzz: 1\n", "{p}: unknown key 'zzz' (known: version, defaults, tenants)"),
])
def test_the_file_and_its_levels(tmp_path: Path, text: str, message: str):
    p, said = _refusal(tmp_path, text)
    assert said == message.format(p=p)


@pytest.mark.parametrize("section,body,message", [
    ("coverage", "5", "defaults.coverage: must be a mapping"),
    ("coverage", "{zzz: 1}", "defaults.coverage: unknown key 'zzz' (known: min, new_code_min)"),
    ("coverage", "{new_code_min: x}", "defaults.coverage.new_code_min: must be a number between 0 and 100 (got 'x')"),
    ("coverage", "{min: true}", "defaults.coverage.min: must be a number between 0 and 100 (got True)"),
    ("harness", "[1]", "defaults.harness: must be a mapping"),
    ("harness", "{max_attempt: 2}", "defaults.harness: unknown key 'max_attempt' — did you mean 'max_attempts'?"),
    ("harness", "{max_attempts: 21}", "defaults.harness.max_attempts: must be an integer between 1 and 20 (got 21)"),
    ("review", "x", "defaults.review: must be a mapping"),
    ("review", "{zzz: 1}", "defaults.review: unknown key 'zzz' (known: spec_approval, adr_when)"),
    ("review", "{spec_approval: maybe}", "defaults.review.spec_approval: must be one of required, optional (got 'maybe')"),
    ("review", "{adr_when: new-module}",
     "defaults.review.adr_when: must be a list of ADR triggers (new-integration, new-module, new-dependency, "
     "contract-change, data-migration) (got 'new-module')"),
    ("knowledge", "null", "defaults.knowledge: must be a mapping"),
    ("knowledge", "{zzz: 1}", "defaults.knowledge: unknown key 'zzz' (known: recurring_after, archive_after_days, "
                              "topics, language)"),
    ("knowledge", "{recurring_after: 1}", "defaults.knowledge.recurring_after: must be an integer between 2 and 100 (got 1)"),
    ("knowledge", "{archive_after_days: 0}",
     "defaults.knowledge.archive_after_days: must be an integer between 1 and 3650 (got 0)"),
    ("knowledge", "{topics: perf}", "defaults.knowledge.topics: must be a list of lowercase topic slugs (got 'perf')"),
    ("knowledge", "{language: english}", "defaults.knowledge.language: must be a language tag (en, pt-BR, es...) (got 'english')"),
])
def test_each_section(tmp_path: Path, section: str, body: str, message: str):
    p, said = _refusal(tmp_path, f"defaults:\n  {section}: {body}\n")
    assert said == f"{p}: {message}"


@pytest.mark.parametrize("text,first", [
    ("defaults:\n  harness: {max_attempts: 0}\n  coverage: {min: 500}\n", "defaults.harness.max_attempts"),
    ("defaults:\n  coverage: {min: 500, zzz: 1}\n", "defaults.coverage.min"),
    ("tenants:\n  acme: [x]\ndefaults:\n  coverage: 5\n", "defaults.coverage: must be a mapping"),
    ("version: 2\nzzz: 1\n", "unknown key 'zzz'"),
    ("tenants:\n  acme:\n    overrides: [x]\n    areas: [x]\n", "tenants.acme.areas"),
    ("tenants:\n  acme:\n    areas:\n      a: {harness: {max_attempts: 0}}\n      b: 5\n", "tenants.acme.areas.a.harness"),
    ("tenants:\n  acme: [x]\n  beta: [y]\n", "tenants.acme:"),
])
def test_with_two_defects_the_one_met_first(tmp_path: Path, text: str, first: str):
    p, said = _refusal(tmp_path, text)
    assert said.startswith(f"{p}: {first}")


def test_bad_yaml(tmp_path: Path):
    p, said = _refusal(tmp_path, "defaults: [\n")
    assert said.startswith(f"invalid YAML in {p}: ") and said != f"invalid YAML in {p}: "


@pytest.mark.parametrize("text", ["", "version: 1\n", "tenants: null\n", "defaults: null\ntenants: {}\n"])
def test_a_file_that_declares_nothing(tmp_path: Path, text: str):
    p = tmp_path / "policy.yaml"
    p.write_text(text)
    policy = load_policy(str(p))
    assert (policy.path, policy.defaults, policy.tenants) == (p, {}, {})
