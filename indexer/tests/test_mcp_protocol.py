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
