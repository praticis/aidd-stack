"""MCP `atlas` protocol test: tools are registered and their Python plumbing works against a fake
store (no Neo4j). Cypher itself is validated by the golden questions (docs/golden-questions.md)."""
from __future__ import annotations

import asyncio
import json
import os

import pytest

from aidd_indexer.mcp.server import Store, _collapse_refs, build_server

EXPECTED_TOOLS = {"atlas_status", "repo_map", "find_symbol", "who_calls", "symbol_context", "http_map",
                  "who_consumes", "impact_of", "ref_diff", "violations", "cypher_readonly"}


class FakeStore(Store):
    def __init__(self):
        self.cfg, self.tenant, self.driver = None, "t", None
        self.queries: list[str] = []

    def ping(self):
        return True

    def resolve_ref(self, repo, ref):
        return ref or "main"

    def read(self, query, **params):
        self.queries.append(query)
        if "sy.name =~ $pattern" in query or "sy.name = $text OR" in query:   # find_symbol precise modes
            return [{"id": "x", "name": params["text"], "pattern": params["pattern"]}]
        if "MATCH (sy:Symbol {tenant: $tenant, role: $role})" in query:   # find_symbol role listing
            return [{"id": "x", "repo": "a", "role": params["role"], "name": "CreateTodoCommandHandler"}]
        if "RETURN sy.id AS id" in query:                       # _symbol
            return [{"id": "t/a@main/sym/pkg.Svc.Do#method", "repo": "a", "ref": "main", "kind": "method", "name": "Do",
                     "qualified_name": "pkg.Svc.Do", "file": "svc.go", "line_start": 1, "line_end": 2, "signature": "func Do()",
                     "doc": "", "visibility": "public", "entry_point": False}]
        if "CALLS*1.." in query:                                # impact_of callers
            return [{"id": "t/a@main/sym/pkg.Handler#function", "qualified_name": "pkg.Handler", "kind": "function",
                     "file": "h.go", "hops": 1, "entry_point": True, "via_ambiguous": False}]
        if "HANDLED_BY {ref: $ref}]->(h:Symbol)" in query and "WHERE h.id IN $ids" in query:
            return [{"endpoint_id": "e1", "service": "a", "method": "GET", "path": "/v1/x", "handler": "pkg.Handler",
                     "consumers": [{"repo": "b", "ref": "main", "caller": "B.Call", "evidence": "b:c.go:1", "confidence": "exact", "hint": None},
                                   {"repo": "b", "ref": "feature/y", "caller": "B.Call", "evidence": "b:c.go:1", "confidence": "exact", "hint": None}]}]
        if "EXPOSES {ref: $ref}]->(e:HttpEndpoint)" in query and "AS key" in query:   # ref_diff endpoints
            return [{"key": "GET /v1/x", "method": "GET", "path": "/v1/x", "handler": "h", "evidence": "a:r.go:1"}] if params["ref"] == "main" \
                else [{"key": "GET /v1/x", "method": "GET", "path": "/v1/x", "handler": "h", "evidence": "a:r.go:1"},
                      {"key": "POST /v1/y", "method": "POST", "path": "/v1/y", "handler": "h2", "evidence": "a:r.go:9"}]
        if "sy.role AS role, count(*) AS count" in query:          # repo_map roles
            return [{"role": "command-handler", "count": 3, "examples": ["CreateTodoCommandHandler"]}]
        if "snap.architecture AS architecture" in query:          # repo_map head
            return [{"stack": ["dotnet"], "architecture": "split", "conventions": ["dotnet-praticis[split]"]}]
        if "RETURN sn.conventions AS c" in query:                 # violations: conventions applied
            return [{"c": ["dotnet-praticis[split]"] if params["repo"] == "a" else None}]
        if "sy.content_hash AS hash" in query:                    # ref_diff symbols
            base = [{"qualified_name": "pkg.Keep", "kind": "function", "file": "k.go", "line": 1, "hash": "1"},
                    {"qualified_name": "pkg.Edit", "kind": "function", "file": "e.go", "line": 1, "hash": "2"},
                    {"qualified_name": "pkg.Gone", "kind": "const", "file": "g.go", "line": 1, "hash": "3"}]
            if params["ref"] == "main":
                return base
            return [base[0], dict(base[1], hash="2b"), {"qualified_name": "pkg.New", "kind": "var", "file": "n.go", "line": 4, "hash": "4"}]
        return []


def _call(srv, name, args):
    result = asyncio.run(srv.call_tool(name, args))
    content = result[0] if isinstance(result, tuple) else result      # (content, structured) in newer SDKs
    return json.loads(content[0].text)


@pytest.fixture()
def server(monkeypatch):
    monkeypatch.setenv("AIDD_TENANT", "t")
    return build_server(store=FakeStore())


def test_tools_registered(server):
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert EXPECTED_TOOLS <= names


def test_impact_of_shape(server):
    out = _call(server, "impact_of", {"symbol": "pkg.Svc.Do", "repo": "a"})
    assert out["internal_caller_count"] == 1 and out["internal_callers"][0]["hops"] == 1
    assert out["internal_callers"][0]["test"] is False and out["production_caller_count"] == 1 and out["test_caller_count"] == 0
    assert [e["path"] for e in out["exposed_through"]] == ["/v1/x"]
    assert out["consumer_repos"] == ["b"]
    assert out["consumers"][0]["refs"] == ["main", "feature/y"]      # collapsed per repo × caller


def test_ref_diff_shape(server):
    out = _call(server, "ref_diff", {"repo": "a", "ref": "feature/y"})
    assert out["base"] == "main"
    assert [e["path"] for e in out["endpoints_added"]] == ["/v1/y"] and out["endpoints_removed"] == []
    assert out["summary"]["endpoints_added"] == 1


def test_ref_diff_same_ref_is_an_error(server):
    with pytest.raises(Exception):
        _call(server, "ref_diff", {"repo": "a", "ref": "main", "base": "main"})


def test_collapse_refs_orders_default_branch_first():
    rows = [{"repo": "a", "ref": "feature/x", "caller": "C", "evidence": "e"}, {"repo": "a", "ref": "main", "caller": "C", "evidence": "e"}]
    assert _collapse_refs(rows)[0]["refs"] == ["main", "feature/x"]


class MultiTenantStore(FakeStore):
    def __init__(self):
        super().__init__()
        self.tenant = None

    def scoped(self, tenant):
        view = MultiTenantStore()
        view.tenant = tenant
        return view

    def read(self, query, **params):
        if "MATCH (r:Repo) RETURN DISTINCT r.tenant" in query:
            return [{"t": "acme"}, {"t": "globex"}]
        if "MATCH (h:RefreshState" in query:
            return [{"last_finished_at": "2026-10-12T10:00:00Z", "last_rc": 0, "trigger": "scheduled",
                     "interval_min": 15, "changed": 0, "age_min": 45}]
        return super().read(query, **params)


def test_raw_cypher_can_be_withdrawn_across_tenants(monkeypatch):
    """Tenant scoping of free Cypher cannot be enforced: offered by default, `ATLAS_RAW_CYPHER=off`
    withdraws it from a multi-tenant atlas (a fixed-tenant one keeps it)."""
    monkeypatch.setenv("AIDD_TENANT", "auto")
    monkeypatch.delenv("ATLAS_RAW_CYPHER", raising=False)
    names = {t.name for t in asyncio.run(build_server(store=MultiTenantStore()).list_tools())}
    assert "cypher_readonly" in names
    monkeypatch.setenv("ATLAS_RAW_CYPHER", "off")
    names = {t.name for t in asyncio.run(build_server(store=MultiTenantStore()).list_tools())}
    assert "cypher_readonly" not in names and "repo_map" in names
    monkeypatch.setenv("AIDD_TENANT", "t")
    names = {t.name for t in asyncio.run(build_server(store=FakeStore()).list_tools())}
    assert "cypher_readonly" in names


def test_atlas_status_reports_refresh_staleness(monkeypatch):
    monkeypatch.setenv("AIDD_TENANT", "auto")
    out = _call(build_server(store=MultiTenantStore()), "atlas_status", {"tenant": "acme"})
    assert out["refresh"]["stale"] is True and out["refresh"]["age_min"] == 45      # > 2 × 15 min
    out = _call(build_server(store=FakeStore()), "atlas_status", {})
    assert out["refresh"]["stale"] is None and "no automatic refresh recorded" in out["refresh"]["note"]


def test_rebinding_hosts_and_foreign_origins_are_refused(server):
    from starlette.testclient import TestClient
    body = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
    hdrs = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    app = server.streamable_http_app()
    with TestClient(app, base_url="http://localhost:3005") as c:
        assert c.post("/mcp", json=body, headers=hdrs).status_code == 200
        assert c.post("/mcp", json=body, headers={**hdrs, "Host": "evil.example:3005"}).status_code in (403, 421)
        assert c.post("/mcp", json=body, headers={**hdrs, "Origin": "http://evil.example"}).status_code == 403
        assert c.post("/mcp", json=body, headers={**hdrs, "Origin": "http://localhost:5173"}).status_code == 200


def test_repo_map_reports_layout_and_roles(server):
    out = _call(server, "repo_map", {"repo": "a"})
    assert out["architecture"] == "split" and out["conventions"] == ["dotnet-praticis[split]"]
    assert out["roles"] == [{"role": "command-handler", "count": 3, "examples": ["CreateTodoCommandHandler"]}]


def test_find_symbol_lists_a_role(server):
    rows = asyncio.run(server.call_tool("find_symbol", {"query": "*", "role": "command-handler", "repo": "a"}))
    content = rows[0] if isinstance(rows, tuple) else rows
    assert json.loads(content[0].text)["role"] == "command-handler"


def test_violations_say_whether_anything_was_checked(server):
    out = _call(server, "violations", {"repo": "a"})
    assert out["checked"] is True and out["conventions"] == ["dotnet-praticis[split]"] and "note" not in out
    out = _call(server, "violations", {"repo": "b"})
    assert out["checked"] is False and out["total"] == 0 and "nothing was checked" in out["note"]


def test_ref_diff_lists_symbols_added_removed_changed(server):
    out = _call(server, "ref_diff", {"repo": "a", "ref": "feature/y"})
    assert [r["qualified_name"] for r in out["symbols_added"]] == ["pkg.New"]
    assert [r["qualified_name"] for r in out["symbols_removed"]] == ["pkg.Gone"]
    assert [r["qualified_name"] for r in out["symbols_changed"]] == ["pkg.Edit"]
    assert out["summary"]["symbols_changed"] == 1 and "hash" not in out["symbols_added"][0]


def test_find_symbol_precise_modes(server):
    def call(args):
        rows = asyncio.run(server.call_tool("find_symbol", args))
        content = rows[0] if isinstance(rows, tuple) else rows
        return json.loads(content[0].text)
    assert call({"query": "Backoff", "match": "word"})["pattern"].startswith("(?s)")
    assert call({"query": "pkg.Do", "match": "exact"})["pattern"] is None
    assert call({"query": "^Err[A-Z]", "match": "regex"})["pattern"] == "(?s).*(?:^Err[A-Z]).*"
    for bad in ({"query": "retry backoff", "match": "word"}, {"query": "a(", "match": "regex"}, {"query": "x", "match": "nope"}):
        with pytest.raises(Exception):
            _call(server, "find_symbol", bad)


@pytest.mark.parametrize("name,hit", [
    ("RetryBackoff", True), ("backoffDelay", True), ("retry_backoff", True), ("BACKOFF_MAX", True),
    ("Backoff", True), ("backoff", True), ("NewBACKOFF", True),
    ("Backoffice", False), ("BackofficeService", False), ("backoffice_user", False), ("myBackoffice", False),
])
def test_word_pattern_is_camel_and_snake_aware(name, hit):
    import re
    from aidd_indexer.mcp.server import _word_pattern
    assert bool(re.fullmatch(_word_pattern("backoff"), name)) is hit       # Neo4j `=~` matches the whole name


def test_atlas_status_reports_remote_sync_per_repo(monkeypatch):
    class Remote(FakeStore):
        def read(self, query, **params):
            if "AS remote" in query:
                return [{"repo": "a", "remote": {"ok": False, "note": "remote fetch failed (404)", "last_success_at": None,
                                                 "success_age_min": None}, "snapshots": []}]
            return super().read(query, **params)
    monkeypatch.setenv("AIDD_TENANT", "t")
    out = _call(build_server(store=Remote()), "atlas_status", {})
    assert out["repos"][0]["remote"]["ok"] is False and "404" in out["repos"][0]["remote"]["note"]
