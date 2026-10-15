"""The indexer build: version + fingerprint of the code that shapes the graph — a change re-indexes."""
from __future__ import annotations

from pathlib import Path

from aidd_indexer.core import build
from aidd_indexer.core.build import fingerprint


def _tree(root: Path) -> Path:
    (root / "core").mkdir(parents=True)
    (root / "core" / "resolve.py").write_text("def resolve(): return 1\n")
    (root / "languages" / "go").mkdir(parents=True)
    (root / "languages" / "go" / "queries.scm").write_text("(call_expression) @call\n")
    (root / "mcp").mkdir()
    (root / "mcp" / "server.py").write_text("TOOLS = 1\n")
    return root


def test_the_fingerprint_follows_the_code_that_shapes_the_graph(tmp_path: Path):
    root = _tree(tmp_path / "pkg")
    first = fingerprint(root)
    assert fingerprint(root) == first and len(first) == 12                    # stable
    (root / "mcp" / "server.py").write_text("TOOLS = 2\n")
    assert fingerprint(root) == first                                          # reading the graph: no re-index
    (root / "core" / "resolve.py").write_text("def resolve(): return 2\n")
    assert fingerprint(root) != first                                          # a resolver change re-indexes
    (root / "core" / "__pycache__").mkdir()
    (root / "core" / "__pycache__" / "resolve.cpython-312.pyc").write_bytes(b"x")
    second = fingerprint(root)
    assert fingerprint(root, extra=[("dotnet-praticis/convention.yaml", b"roles: {}")]) != second   # convention packages count


def test_a_snapshot_of_another_build_is_reindexed(monkeypatch):
    from aidd_indexer.core.graph import current_sha
    import aidd_indexer.core.graph as graph
    monkeypatch.setattr(graph, "indexer_build", lambda: "0.2.14+aaaaaaaaaaaa")
    assert current_sha("abc", "0.2.14+aaaaaaaaaaaa") == "abc"
    assert current_sha("abc", "0.2.14+bbbbbbbbbbbb") == ""     # same version, other code
    assert current_sha("abc", None) == ""                      # written before builds were recorded


def test_the_running_build_names_the_version():
    from aidd_indexer import INDEXER_VERSION
    assert build.indexer_build().startswith(INDEXER_VERSION + "+")
