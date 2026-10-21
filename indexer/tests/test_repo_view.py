"""A scanner learns about other directories by asking the view one question at a time, never by walking their
contexts: each lookup then has one answer for the whole repo, the one a scan that saw only some directories is
checked against."""

import ast
import contextlib
import io
from pathlib import Path

import pytest

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


GO_ROOT = {
    "go.mod": "module example.com/x\n\ngo 1.22\n",
    "x.go": "package x\n\nfunc Path(p string) string { return p }\n",
    "paths/paths.go": "package paths\n\nfunc Path(p string) string { return p }\n",
    "client/client.go": """package client

import (
	"net/http"

	"example.com/x"
	"example.com/x/paths"
)

func calls() {
	http.Get(x.Path("/users"))
	http.Get(paths.Path("/items"))
}
""",
}


@pytest.mark.xfail(strict=True, reason="Go reads an imported package's directory by `view.contexts.get`, which has "
                   "no entry for the root package's path \"\" (the root directory's key is \".\")")
def test_a_function_of_the_root_package_is_read_like_any_other(tmp_path):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, body in GO_ROOT.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(body)
    repo = RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(tmp_path))
    with contextlib.redirect_stderr(io.StringIO()):
        res, _ = extract_and_resolve(repo)
    assert {c.path for c in res.http_calls} == {"/users", "/items"}
