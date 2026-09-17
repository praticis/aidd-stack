"""Golden-file regression for the HTTP integration extractor.

Each folder under tests/fixtures/<name>/ is a tiny repository with an `expected.json` written
by hand (or reviewed line by line) listing the routes it exposes and the outbound calls it
makes. Precision and recall must both be 100 % on fixtures — they are controlled code.

    cd indexer && pip install -e . && pytest -q tests/
Grammars must be cached (TREE_SITTER_LANGUAGE_PACK_CACHE_DIR) — see docs/indexer-evolution.md §4.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = sorted(p for p in (Path(__file__).parent / "fixtures").iterdir() if (p / "expected.json").exists())


def _extract(root: Path):
    from aidd_indexer.cli import extract_tree
    from aidd_indexer.integrations import extract_http
    from aidd_indexer.model import RepoInfo

    repo = RepoInfo(tenant="t", name=root.name, ref="main", commit_sha="x", root=str(root))
    res, extractors = extract_tree(repo)
    return extract_http(repo, extractors)


@pytest.mark.parametrize("root", FIXTURES, ids=[p.name for p in FIXTURES])
def test_fixture(root: Path):
    expected = json.loads((root / "expected.json").read_text())
    hr = _extract(root)
    got_eps = sorted({(e.method, e.path, e.handler_name) for e in hr.endpoints})
    exp_eps = sorted({(e["method"], e["path"], e.get("handler")) for e in expected["endpoints"]})
    assert got_eps == exp_eps, f"endpoints differ\n missing={set(exp_eps)-set(got_eps)}\n extra={set(got_eps)-set(exp_eps)}"
    got_calls = sorted({(c.method, c.path, c.line) for c in hr.calls})
    exp_calls = sorted({(c["method"], c["path"], c["line"]) for c in expected["calls"]})
    assert got_calls == exp_calls, f"calls differ\n missing={set(exp_calls)-set(got_calls)}\n extra={set(got_calls)-set(exp_calls)}"
    assert not hr.warnings, hr.warnings
