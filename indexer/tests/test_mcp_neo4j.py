"""Every atlas tool against a real Neo4j holding a small indexed graph: a Go service `orders` (`GET /v1/orders/{id}`,
whose handler calls `loadOrder`; on the branch `feature/items` also `GET /v1/orders/{id}/items`), an ASP.NET service
`accounts` (`/api/Accounts/{id}/details`, as `[controller]` writes it; its controller imports three of its own
namespaces, one module under three specs, and its action reaches `INotifier.Notify`, which `Notifier` implements and
`AuditNotifier` overrides, while a call on a `PlainNotifier` runs `Notifier`'s only) and a TS client `shop` that calls
both, the second in lower case. Run by
`scripts/mcp-it.sh`, which starts that Neo4j; skipped without it."""

import asyncio
import json
import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("NEO4J_URI"), reason="needs the Neo4j that scripts/mcp-it.sh starts")


@pytest.fixture(scope="module")
def srv():
    from aidd_indexer.core.config import Neo4jConfig
    from aidd_indexer.mcp.server import Store, build_server
    store = Store(Neo4jConfig.from_env(), "it")
    yield build_server(store=store)
    store.close()


def call(srv, name, **args):
    result = asyncio.run(srv.call_tool(name, args))
    content = result[0] if isinstance(result, tuple) else result
    return json.loads(content[0].text)


def call_list(srv, name, **args):
    """A tool that returns a list: one content item per element."""
    result = asyncio.run(srv.call_tool(name, args))
    content = result[0] if isinstance(result, tuple) else result
    return [json.loads(c.text) for c in content]


def test_atlas_status_lists_both_repositories_and_the_branch(srv):
    repos = {r["repo"]: {s["ref"] for s in r["snapshots"]} for r in call(srv, "atlas_status")["repos"]}
    assert repos == {"orders": {"main", "feature/items"}, "accounts": {"main"}, "shop": {"main"}}


def test_repo_map(srv):
    out = call(srv, "repo_map", repo="orders")
    assert out["ref"] == "main" and out["modules"] and out["symbol_kinds"].get("function")


def test_find_symbol(srv):
    rows = call_list(srv, "find_symbol", query="getOrder", repo="orders", match="exact")
    assert [r["name"] for r in rows] == ["getOrder"]


def test_who_calls_and_symbol_context(srv):
    callers = call(srv, "who_calls", symbol="loadOrder", repo="orders")["callers"]
    assert [c["qualified_name"] for c in callers] == ["getOrder"]
    ctx = call(srv, "symbol_context", symbol="getOrder", repo="orders")
    assert "loadOrder" in [c["qualified_name"] for c in ctx["calls"]]


def test_symbol_context_lists_a_files_imports_in_one_order(srv):
    imports = call(srv, "symbol_context", symbol="Accounts.Api.AccountsController", repo="accounts")["file_imports"]
    keys = [(i["type"], i["target"], i["spec"]) for i in imports]
    assert keys == sorted(keys) and [i["spec"] for i in imports if i["type"] == "Module"] == \
        ["Accounts.Dto", "Accounts.Models", "Accounts.Services"]


def test_http_map_of_the_service_and_of_its_client(srv):
    exposes = call(srv, "http_map", repo="orders")["exposes"]
    route = next(e for e in exposes if e["path"] == "/v1/orders/{id}")
    assert route["method"] == "GET" and route["consumer_repos"] == ["shop"] and route["app"] == ""
    shop = call(srv, "http_map", repo="shop")
    assert shop["outbound_linked"] == 2
    assert sorted(c["linked_to"]["service"] for c in shop["outbound_calls"]) == ["accounts", "orders"]


@pytest.mark.parametrize("asked", ["/v1/orders/{id}", "/v1/orders/:id", "v1/orders/{orderId}/"])
def test_who_consumes(srv, asked):
    endpoints = call(srv, "who_consumes", path=asked)["endpoints"]
    assert [(e["service"], e["consumer_repos"]) for e in endpoints if e["path"] == "/v1/orders/{id}"] == [("orders", ["shop"])]


def test_impact_of_reaches_the_route_and_its_consumer(srv):
    out = call(srv, "impact_of", symbol="loadOrder", repo="orders")
    assert [e["path"] for e in out["exposed_through"]] == ["/v1/orders/{id}"] and out["consumer_repos"] == ["shop"]


def test_who_calls_an_override_lists_the_dispatching_calls_that_may_run_it(srv):
    out = call(srv, "who_calls", symbol="AuditNotifier.Notify", repo="accounts")
    assert out["callers"] == [] and out["overridden_by"] == []
    assert [o["qualified_name"] for o in out["overrides"]] == \
        ["Accounts.Notifications.INotifier.Notify", "Accounts.Notifications.Notifier.Notify"]
    assert [(c["qualified_name"], c["line"], c["via"]) for c in out["dispatched_callers"]] == [
        ("Accounts.Services.AccountService.MarkSeen", 33, "Accounts.Notifications.INotifier.Notify"),
        ("Accounts.Services.AccountService.MarkSeen", 33, "Accounts.Notifications.Notifier.Notify")]
    # neither its own base call nor a call on a PlainNotifier, which never holds an AuditNotifier


def test_who_calls_a_base_method_lists_its_overrides_without_their_callers(srv):
    out = call(srv, "who_calls", symbol="Notifier.Notify", repo="accounts")
    assert [(c["qualified_name"], c["line"]) for c in out["callers"]] == [
        ("Accounts.Notifications.AuditNotifier.Notify", 15), ("Accounts.Notifications.Alerts.Plain", 24),
        ("Accounts.Services.AccountService.MarkSeen", 33)]
    assert [(c["qualified_name"], c["via"]) for c in out["dispatched_callers"]] == [
        ("Accounts.Services.AccountService.MarkSeen", "Accounts.Notifications.INotifier.Notify")]
    assert [o["qualified_name"] for o in out["overridden_by"]] == ["Accounts.Notifications.AuditNotifier.Notify"]


def test_impact_of_an_override_reaches_the_route_through_a_dispatch(srv):
    out = call(srv, "impact_of", symbol="AuditNotifier.Notify", repo="accounts")
    assert [(c["qualified_name"], c["hops"], c["via_dispatch"]) for c in out["internal_callers"]] == [
        ("Accounts.Services.AccountService.MarkSeen", 1, True), ("Accounts.Api.AccountsController.Details", 2, True)]
    assert [e["path"] for e in out["exposed_through"]] == ["/api/Accounts/{id}/details"]
    assert out["consumer_repos"] == ["shop"]
    base = call(srv, "impact_of", symbol="Notifier.Notify", repo="accounts")["internal_callers"]
    assert [(c["qualified_name"], c["hops"], c["via_dispatch"]) for c in base] == [
        ("Accounts.Notifications.Alerts.Plain", 1, False), ("Accounts.Notifications.AuditNotifier.Notify", 1, False),
        ("Accounts.Services.AccountService.MarkSeen", 1, False), ("Accounts.Api.AccountsController.Details", 2, False)]


def test_ref_diff_shows_the_branchs_route(srv):
    out = call(srv, "ref_diff", repo="orders", ref="feature/items")
    assert [(e["method"], e["path"]) for e in out["endpoints_added"]] == [("GET", "/v1/orders/{id}/items")]


def test_violations_say_nothing_was_checked(srv):
    out = call(srv, "violations", repo="orders")
    assert out["checked"] is False and out["total"] == 0


def test_cypher_readonly_reads_and_refuses_writes(srv):
    rows = call(srv, "cypher_readonly", query="MATCH (r:Repo {tenant: $tenant}) RETURN count(r) AS n")["rows"]
    assert rows == [{"n": 3}]
    with pytest.raises(Exception):
        call(srv, "cypher_readonly", query="CREATE (n:Probe) RETURN n")


@pytest.mark.parametrize("asked", ["/api/accounts/{id}/details", "/api/Accounts/{accountId}/details"])
def test_an_aspnet_route_is_found_and_linked_without_case(srv, asked):
    endpoints = call(srv, "who_consumes", path=asked)["endpoints"]
    assert [(e["service"], e["path"], e["consumer_repos"]) for e in endpoints] == \
        [("accounts", "/api/Accounts/{id}/details", ["shop"])]
