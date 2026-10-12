"""Call resolution in C# (F0.7.2): receiver types from fields/properties/locals, inherited members
from in-repo bases, and interface -> unique implementer."""
from __future__ import annotations

import contextlib
import io
from pathlib import Path

FIX = Path(__file__).parent / "fixtures" / "csharp-receiver-types"


def _edges():
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    repo = RepoInfo(tenant="t", name=FIX.name, ref="main", commit_sha="x", root=str(FIX))
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(repo)
    sym = {s.id: s for s in res.symbols}
    out: dict[tuple[int, str], list[tuple[str, str]]] = {}
    for e in rv.calls:
        caller = sym.get(e.caller_id)
        if caller is not None and caller.name == "FindByIdAsync":
            out.setdefault((e.line, sym[e.callee_id].name), []).append((sym[e.callee_id].qualified_name, e.strategy))
    return out


def test_interface_field_links_to_interface_and_unique_implementer():
    e = _edges()[(18, "FindByIdAsync")]
    assert ("Shop.Api.Queries.IAccountQuery.FindByIdAsync", "receiver-type") in e
    assert ("Shop.Api.Infra.AccountReadRepository.FindByIdAsync", "receiver-type-impl") in e
    assert not any(q.endswith("AccountsController.FindByIdAsync") for q, _ in e)      # no self-call by homonym


def test_explicit_impl_of_another_interface_is_not_a_target():
    e = _edges()
    assert (22, "FindByIdAsync") not in e                      # `_accounts.FindByIdAsync` (IAccountReadRepository): no edge at all
    assert e[(18, "FindByIdAsync")] and all("IAccountQuery" in q or "AccountReadRepository" in q for q, _ in e[(18, "FindByIdAsync")])


def test_property_and_inherited_base_member():
    assert _edges()[(19, "CountAsync")] == [("Shop.Api.Infra.BaseReadRepository.CountAsync", "receiver-type")]


def test_local_new_picks_the_right_homonym():
    assert _edges()[(21, "Describe")] == [("Shop.Api.Infra.GroupReadRepository.Describe", "receiver-type")]


THIS_BASE = """namespace Shop.Api.Infra;

public class TodoReadRepository : BaseReadRepository<TodoModel, Guid>, ITodoReadRepository
{
    public bool Exists(string name) => true;

    public bool NotExists(string name) => !this.Exists(name);

    public override Task<TodoModel?> FindByIdAsync(Guid id, CancellationToken ct) => base.FindByIdAsync(id, ct);
}
"""


def test_this_and_base_calls(tmp_path: Path):
    """`this.X()` / `base.X()` are call sites (the receivers are anonymous tokens in the grammar); a
    `base.X()` whose base type lives in a package resolves to nothing — never to the override itself."""
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    root = tmp_path / "shop"
    (root / "src/Shop.Api/Infra").mkdir(parents=True)
    (root / "src/Shop.Api/Shop.Api.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk.Web"></Project>\n')
    (root / "src/Shop.Api/Infra/TodoReadRepository.cs").write_text(THIS_BASE)
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="shop", ref="main", commit_sha="x", root=str(root)), convs=[])
    sym = {s.id: s.name for s in res.symbols}
    assert {(c.callee_name, c.receiver) for c in res.calls} >= {("Exists", "this"), ("FindByIdAsync", "base")}
    assert [(sym[e.caller_id], sym[e.callee_id], e.strategy) for e in rv.calls] == [("NotExists", "Exists", "receiver-type")]


def test_base_call_without_base_list_is_not_a_self_edge(tmp_path: Path):
    """`partial class View` (base declared in XAML) or implicit `object`: `base.X()` has no type at all."""
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    root = tmp_path / "app"
    root.mkdir()
    (root / "View.cs").write_text("namespace App;\n\npublic partial class View\n{\n"
                                  "    protected override void OnAppearing() { base.OnAppearing(); }\n}\n")
    with contextlib.redirect_stderr(io.StringIO()):
        _, rv = extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root)), convs=[])
    assert rv.calls == []
