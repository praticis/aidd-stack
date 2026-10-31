"""Go's calls, where the resolver still reaches no method of the repo that the call runs. Each case states the right
answer and is a strict xfail with the reason: when the resolver learns it, the case passes, the xfail fails the suite,
and the mark has to go."""

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


def case(id, files, why):
    return pytest.param(files, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


CASES = [
    case("a-call-on-an-interface-of-two-implementers-reaches-its-method", STORE,
         "an interface's methods are not symbols, and two implementers are no single target"),
]


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
