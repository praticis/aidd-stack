"""A store with no Neo4j for the `atlas` tools' tests: each query is answered by the first row of `ANSWERS` whose
matcher takes it, or with no rows. Each answer is built anew, since a tool may change the rows it is given."""
from __future__ import annotations

from typing import Any, Callable

from aidd_indexer.mcp.server import Store

Matcher = Callable[[str], bool]
Answer = Callable[[str, dict[str, Any]], list[dict[str, Any]]]


def any_of(*parts: str) -> Matcher:
    return lambda query: any(p in query for p in parts)


def all_of(*parts: str) -> Matcher:
    return lambda query: all(p in query for p in parts)


def _impact(query, ids):
    if "AS dispatch" in query:
        return [{"caller": "t/a@main/sym/pkg.Handler#function", "callee": i, "strategy": "receiver-type",
                 "dispatch": False} for i in ids if i == "t/a@main/sym/pkg.Svc.Do#method"]
    return [{"id": i, "qualified_name": i.split("/sym/")[1].split("#")[0], "kind": "function", "file": "h.go",
             "entry_point": True} for i in ids]


def _symbol(query, params):
    return [{"id": "t/a@main/sym/pkg.Svc.Do#method", "repo": "a", "ref": "main", "kind": "method", "name": "Do",
             "qualified_name": "pkg.Svc.Do", "file": "svc.go", "line_start": 1, "line_end": 2, "signature": "func Do()",
             "doc": "", "visibility": "public", "entry_point": False}]


def _exposed(query, params):
    return [{"endpoint_id": "e1", "service": "a", "method": "GET", "path": "/v1/x", "handler": "pkg.Handler",
             "consumers": [{"repo": "b", "ref": "main", "caller": "B.Call", "evidence": "b:c.go:1", "confidence": "exact", "hint": None},
                           {"repo": "b", "ref": "feature/y", "caller": "B.Call", "evidence": "b:c.go:1", "confidence": "exact", "hint": None}]}]


def _ref_endpoints(query, params):
    return [{"key": "GET /v1/x", "method": "GET", "path": "/v1/x", "handler": "h", "evidence": "a:r.go:1"}] if params["ref"] == "main" \
        else [{"key": "GET /v1/x", "method": "GET", "path": "/v1/x", "handler": "h", "evidence": "a:r.go:1"},
              {"key": "POST /v1/y", "method": "POST", "path": "/v1/y", "handler": "h2", "evidence": "a:r.go:9"}]


def _ref_symbols(query, params):
    base = [{"qualified_name": "pkg.Keep", "kind": "function", "file": "k.go", "line": 1, "hash": "1"},
            {"qualified_name": "pkg.Edit", "kind": "function", "file": "e.go", "line": 1, "hash": "2"},
            {"qualified_name": "pkg.Gone", "kind": "const", "file": "g.go", "line": 1, "hash": "3"}]
    if params["ref"] == "main":
        return base
    return [base[0], dict(base[1], hash="2b"), {"qualified_name": "pkg.New", "kind": "var", "file": "n.go", "line": 4, "hash": "4"}]


ANSWERS: list[tuple[Matcher, Answer]] = [
    (any_of("sy.name =~ $pattern", "sy.name = $text OR"),                  # find_symbol precise modes
     lambda q, p: [{"id": "x", "name": p["text"], "pattern": p["pattern"]}]),
    (any_of("MATCH (sy:Symbol {tenant: $tenant, role: $role})"),           # find_symbol role listing
     lambda q, p: [{"id": "x", "repo": "a", "role": p["role"], "name": "CreateTodoCommandHandler"}]),
    (any_of("RETURN sy.id AS id"), _symbol),                               # _symbol
    (any_of("UNWIND $ids AS id"), lambda q, p: _impact(q, p["ids"])),      # impact_of: a hop of callers, then the callers found
    (all_of("HANDLED_BY {ref: $ref}]->(h:Symbol)", "WHERE h.id IN $ids"), _exposed),
    (all_of("EXPOSES {ref: $ref}]->(e:HttpEndpoint)", "AS key"), _ref_endpoints),
    (any_of("sy.role AS role, count(*) AS count"),                         # repo_map roles
     lambda q, p: [{"role": "command-handler", "count": 3, "examples": ["CreateTodoCommandHandler"]}]),
    (any_of("snap.architecture AS architecture"),                          # repo_map head
     lambda q, p: [{"stack": ["dotnet"], "architecture": "split", "conventions": ["dotnet-praticis[split]"]}]),
    (any_of("RETURN sn.conventions AS c"),                                 # violations: conventions applied
     lambda q, p: [{"c": ["dotnet-praticis[split]"] if p["repo"] == "a" else None}]),
    (any_of("sy.content_hash AS hash"), _ref_symbols),
]


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
        return next((answer(query, params) for matches, answer in ANSWERS if matches(query)), [])
