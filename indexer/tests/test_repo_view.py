"""A scanner learns about other directories by asking the view one question at a time, never by walking their
contexts: each lookup then has one answer for the whole repo, the one a scan that saw only some directories is
checked against."""

import ast
from pathlib import Path

from aidd_indexer.core.http_base import PackageContext
from aidd_indexer.core.http_view import RepoView

PACKAGE = Path(__file__).resolve().parents[1] / "aidd_indexer"
VIEW = "core/http_view.py"


def _walks(tree: ast.AST) -> list[int]:
    """Lines that use `.contexts` other than to read one directory (`.contexts.get(d)`)."""
    one = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "get"}
    return [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Attribute) and n.attr == "contexts" and id(n) not in one]


def test_only_the_view_walks_the_directories():
    found = [f"{f.relative_to(PACKAGE).as_posix()}:{line}" for f in sorted(PACKAGE.rglob("*.py"))
             if f.relative_to(PACKAGE).as_posix() != VIEW for line in _walks(ast.parse(f.read_text()))]
    assert found == []


def test_a_constant_has_the_values_the_directories_give_it():
    a, b, c, d = PackageContext(), PackageContext(), PackageContext(), PackageContext()
    a.define("Web.Root", raw="/api")
    b.define("Web.Root", parts=[("lit", "/api")])
    c.define("Web.Path", parts=[("lit", "~/"), ("ref", "Segment")])
    c.define("Segment", segment="app")
    d.define("Web.Root", raw="/a")
    d.define("Web.Root", raw="/b")                     # two values in one directory: it gives none
    view = RepoView(None, [], None, {"a": a, "b": b, "c": c, "d": d})
    assert view.constant_values("Web.Root") == {"/api"}
    assert view.constant_values("Web.Path") == {"~/app"}
    assert view.constant_values("Web.Other") == set()
