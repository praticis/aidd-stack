"""F0.5 linker: HttpCall × HttpEndpoint → CONSUMES / CALLED_FROM. Unit rules + the fixture pair
(go-http-mix calls go-billing-api; py-notifications-api also exposes /health)."""
from __future__ import annotations

from pathlib import Path

from aidd_indexer.core.linker import CallRow, EndpointRow, called_from_rows, consumes_rows, link

FIXTURES = Path(__file__).parent / "fixtures"


def ep(service, method, path_key, id=None):
    return EndpointRow(id or f"t/svc/{service}/http/{method} {path_key}", service, method, path_key)


def call(repo, method, path_key, target_hint="", env_hints=(), id="c1"):
    return CallRow(id=id, repo=repo, ref="main", commit_sha="x", method=method, path_key=path_key,
                   target_hint=target_hint, env_hints=tuple(env_hints), caller_id=f"{repo}/sym", evidence=f"{repo}:f.go:1",
                   via="c.Get", line=1)


def test_exact_match_and_method_any():
    r = link([call("a", "GET", "/v1/x"), call("a", "POST", "/v1/y", id="c2")],
             [ep("b", "GET", "/v1/x"), ep("b", "ANY", "/v1/y")])
    assert [(e.endpoint.service, e.confidence) for e in r.edges] == [("b", "exact"), ("b", "exact")]


def test_method_mismatch_is_unmatched():
    r = link([call("a", "POST", "/v1/x")], [ep("b", "GET", "/v1/x")])
    assert not r.edges and len(r.unmatched) == 1


def test_never_links_to_own_service():
    r = link([call("a", "GET", "/v1/x")], [ep("a", "GET", "/v1/x")])
    assert not r.edges and len(r.unmatched) == 1


def test_suffix_needs_segment_alignment_and_a_hint():
    eps = [ep("billing-api", "GET", "/internal/v1/users/{param}")]
    r = link([call("a", "GET", "/v1/users/{param}", target_hint="billing")], eps)
    assert [e.confidence for e in r.edges] == ["suffix"]
    r = link([call("a", "GET", "/v1/users/{param}", env_hints=["BILLING_URL"])], eps)
    assert [e.confidence for e in r.edges] == ["suffix"]
    r = link([call("a", "GET", "/v1/users/{param}", target_hint="storage")], eps)
    assert not r.edges and len(r.unmatched) == 1                  # tail of an unrelated route: no hint, no edge
    r = link([call("a", "GET", "/users/{param}", target_hint="billing")], [ep("billing-api", "GET", "/v1/xusers/{param}")])
    assert not r.edges                                            # "xusers" is not a segment boundary
    r = link([call("a", "GET", "/v1/x", target_hint="c")], [ep("b", "GET", "/v1/x"), ep("c", "GET", "/api/v1/x")])
    assert [e.endpoint.service for e in r.edges] == ["b"]        # exact wins, suffix candidates ignored


def test_ambiguous_writes_nothing_and_hints_break_ties():
    eps = [ep("billing-api", "GET", "/health"), ep("notifications", "GET", "/health")]
    r = link([call("a", "GET", "/health")], eps)
    assert not r.edges and list(r.ambiguous) == ["c1"] and len(r.ambiguous["c1"]) == 2
    r = link([call("a", "GET", "/health", target_hint="billing")], eps)
    assert [(e.endpoint.service, e.hint) for e in r.edges] == [("billing-api", "target_hint")]
    r = link([call("a", "GET", "/health", target_hint="http", env_hints=["NOTIFICATIONS_URL"])], eps)
    assert [(e.endpoint.service, e.hint) for e in r.edges] == [("notifications", "env_hint")]
    r = link([call("a", "GET", "/health", target_hint="api", env_hints=["BASE_URL"])], eps)
    assert not r.edges and "c1" in r.ambiguous                    # generic tokens never disambiguate


def test_rows_collapse_call_sites_per_endpoint():
    eps = [ep("b", "GET", "/v1/x")]
    r = link([call("a", "GET", "/v1/x", id="c1"), call("a", "GET", "/v1/x", id="c2")], eps)
    rows = consumes_rows(r)
    assert len(rows) == 1 and rows[0]["call_count"] == 2 and rows[0]["confidence"] == "exact"
    assert [x["call_id"] for x in called_from_rows(r)] == ["c1", "c2"]


def _extract(name: str):
    from aidd_indexer.cli import extract_tree
    from aidd_indexer.core.integrations import extract_http
    from aidd_indexer.core.model import RepoInfo
    root = FIXTURES / name
    repo = RepoInfo(tenant="t", name=name, ref="main", commit_sha="x", root=str(root))
    _, extractors = extract_tree(repo)
    return extract_http(repo, extractors)


def test_fixture_pair_links_end_to_end():
    from aidd_indexer.core.paths import path_key
    endpoints, calls = [], []
    for name in ("go-http-mix", "go-billing-api", "py-notifications-api"):
        hr = _extract(name)
        endpoints += [EndpointRow(e.id, name, e.method, path_key(e.path)) for e in hr.endpoints]
        calls += [CallRow(c.id, name, "main", "x", c.method, path_key(c.path), c.target_hint, tuple(c.env_hints),
                          c.caller_id, c.evidence, c.via, c.line) for c in hr.calls]
    r = link(calls, endpoints)
    got = sorted((e.call.path_key, e.endpoint.service, e.endpoint.path_key, e.confidence, e.hint) for e in r.edges)
    assert got == [
        ("/health", "go-billing-api", "/health", "exact", "target_hint"),            # two services expose it; target_hint=billing
        ("/v1/auth/failed-attempt", "go-billing-api", "/v1/auth/failed-attempt", "exact", None),
        ("/v1/users/{param}", "go-billing-api", "/internal/v1/users/{param}", "suffix", None),
        ("/v1/users/{param}/sessions", "go-billing-api", "/v1/users/{param}/sessions", "exact", None),
    ]
    assert not r.unmatched and not r.ambiguous
