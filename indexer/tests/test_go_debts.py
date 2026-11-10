"""Go's calls, where the resolver still reaches no method of the repo that the call runs, or reaches one it cannot run.
Each case states the right answer and is a strict xfail with the reason: when the resolver learns it, the case passes,
the xfail fails the suite, and the mark has to go."""

import contextlib
import io

import pytest

STORE = {
    "go.mod": "module example.com/app\n\ngo 1.22\n",
    "store.go": """package app

type Store interface{ Get() string }

type Memory struct{}

func (Memory) Get() string { return "" }

type Disk struct{}

func (Disk) Get() string { return "" }

func Use(s Store) string { return s.Get() }
""",
}


BUILTIN = {
    "go.mod": "module example.com/app\n\ngo 1.22\n",
    "queue.go": """package app

type Queue struct{ items []int }

func (q Queue) len() int { return 0 }

func (q Queue) string() string { return "" }

func Count(x []int) int { return len(x) }

func Text(b []byte) string { return string(b) }
""",
}
PACKAGES = {
    "go.mod": "module example.com/app\n\ngo 1.22\n",
    "db/db.go": "package db\n\nfunc Open() int { return 0 }\n",
    "cache/cache.go": "package cache\n\nfunc Open() int { return 1 }\n",
    "svc/svc.go": 'package svc\n\nimport (\n\t"example.com/app/cache"\n\t"example.com/app/db"\n)\n\nfunc Run() {\n'
                  "\tdb.Open()\n\tcache.Open()\n}\n",
}


def case(id, files, why):
    return pytest.param(files, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


CASES = [
    case("a-call-on-an-interface-of-two-implementers-reaches-its-method", STORE,
         "an interface's methods are not symbols, and two implementers are no single target"),
]
NO_METHOD = [
    case("a-go-call-of-a-builtin-or-a-conversion-reaches-no-method", BUILTIN,
         "finds a bare name among the homonyms of the file, methods included, where a bare name calls a function"),
]
QUALIFIED = [
    case("a-package-qualified-call-reaches-the-function-of-that-package", PACKAGES,
         "finds the function by its name alone, so a name two packages declare reaches none, and the import path is not read"),
]


def _edges(root, files) -> set[tuple[str, str]]:
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root)),
                                      convs=[])
    q = {s.id: s.qualified_name for s in res.symbols}
    return {(q.get(c.caller_id, ""), q[c.callee_id]) for c in rv.calls}


@pytest.mark.parametrize("files", CASES)
def test_a_call_on_an_interface_reaches_the_interfaces_method(tmp_path, files):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, body in files.items():
        (tmp_path / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(tmp_path)),
                                      convs=[])
    q = {s.id: s.qualified_name for s in res.symbols}
    store = next(s.qualified_name for s in res.symbols if s.name == "Store")
    assert {q[c.callee_id] for c in rv.calls if q.get(c.caller_id, "").endswith("Use")} == {f"{store}.Get"}


@pytest.mark.parametrize("files", NO_METHOD)
def test_a_bare_name_call_reaches_no_method(tmp_path, files):
    assert not {edge for edge in _edges(tmp_path, files) if edge[0] in {"Count", "Text"}}


@pytest.mark.parametrize("files", QUALIFIED)
def test_a_package_qualified_call_reaches_the_function_of_its_package(tmp_path, files):
    assert {callee for caller, callee in _edges(tmp_path, files) if caller == "svc.Run"} == {"db.Open", "cache.Open"}
