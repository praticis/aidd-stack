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
