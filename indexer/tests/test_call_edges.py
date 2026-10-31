"""A `CALLS` edge is its caller, callee, line and method: the calls of one line that reach one target are one edge, by the
strongest of their strategies, and two methods of a package base reached on one line are two edges. The graph writer
creates one edge per call the resolver gives."""
from __future__ import annotations

import contextlib
import io
from pathlib import Path

ACCOUNTS = Path(__file__).parent / "mcp_it" / "accounts"


def _calls(caller: str) -> list[tuple[str, str, str | None]]:
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    repo = RepoInfo(tenant="t", name="accounts", ref="main", commit_sha="x", root=str(ACCOUNTS))
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(repo)
    names = {s.id: s.qualified_name for s in res.symbols}
    return [(names[c.callee_id], c.strategy, c.method) for c in rv.calls
            if names.get(c.caller_id) == f"Accounts.Services.AccountService.{caller}"]


def test_a_target_the_receivers_type_and_its_implementation_both_reach_is_one_edge_by_the_type():
    # the implementation declares no `SaveChanges`: through its own bases it reaches the interface's again
    assert _calls("Save") == [("Accounts.Services.IAccountsDb.SaveChanges", "receiver-type", None)]


def test_two_methods_of_a_package_base_on_one_line_are_two_edges():
    assert _calls("Track") == [("Accounts.Services.AccountsDb", "inherited", "Add"),
                               ("Accounts.Services.AccountsDb", "inherited", "Remove")]


def test_the_strongest_strategy_holds_the_edge_where_its_first_call_was():
    from aidd_indexer.core.edges import CallEdge, one_per_edge
    calls = [CallEdge("a", "b", 1, "same-module"), CallEdge("a", "c", 1, "same-file-ambiguous"),
             CallEdge("a", "b", 1, "receiver-type"), CallEdge("a", "c", 1, "same-file"),
             CallEdge("a", "c", 2, "same-file"), CallEdge("a", "b", 1, "inherited", "Add")]
    assert one_per_edge(calls) == [CallEdge("a", "b", 1, "receiver-type"), CallEdge("a", "c", 1, "same-file"),
                                   CallEdge("a", "c", 2, "same-file"), CallEdge("a", "b", 1, "inherited", "Add")]
