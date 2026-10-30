"""What a C# receiver's type reaches, where the resolver still misses it. Each case states the right answer and is a
strict xfail with the reason: when the resolver learns it, the case passes, the xfail fails the suite, and the mark has
to go."""

import contextlib
import io

import pytest

STORE = """using Microsoft.EntityFrameworkCore;

namespace Api.Services;

public interface IStore
{
    int SaveChanges();
}

public class Store : DbContext, IStore
{
}

public class Runner
{
    private readonly IStore _store;

    public Runner(IStore store) { _store = store; }

    public int Run() => _store.SaveChanges();
}
"""


def case(id, source, expected, why):
    return pytest.param(source, expected, id=id, marks=pytest.mark.xfail(strict=True, reason=f"the resolver {why}"))


CASES = [
    case("an-implementation-whose-method-a-package-base-gives-is-reached", STORE,
         {("Api.Services.IStore.SaveChanges", "receiver-type", None), ("Api.Services.Store", "inherited-impl", "SaveChanges")},
         "looks the implementation's method up through the interfaces it implements, and finds the interface's own"),
]


def _edges(root, source: str) -> set[tuple[str, str, str | None]]:
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, text in {"Api.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>', "Services/Store.cs": source}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)))
    names = {s.id: s.qualified_name for s in res.symbols}
    return {(names[c.callee_id], c.strategy, c.method) for c in rv.calls if names.get(c.caller_id) == "Api.Services.Runner.Run"}


@pytest.mark.parametrize("source,expected", CASES)
def test_the_call_reaches_the_implementation_csharp_runs(tmp_path, source, expected):
    assert _edges(tmp_path, source) == expected
