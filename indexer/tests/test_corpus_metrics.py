"""Corpus measurement (scripts/corpus_metrics.py): run diffs, precision/recall against a gabarito,
OpenAPI → gabarito and reproducible samples. No network, no tree-sitter."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import corpus_metrics as M  # noqa: E402


def ep(method, path, evidence, handler_id=None):
    return {"method": method, "path": path, "evidence": evidence, "handler_id": handler_id, "raw_pattern": path}


def call(method, path, evidence, caller_id="c"):
    return {"method": method, "path": path, "evidence": evidence, "caller_id": caller_id, "raw_path": path}


RUN = {"sha": "abc",
       "endpoints": [ep("GET", "/v1/items/{id}", "r:api/items.go:10", "h1"),
                     ep("POST", "/v1/items", "r:api/items.go:11", "h2"),
                     ep("ANY", "/health", "r:main.go:5"),
                     ep("GET", "/debug/vars", "r:internal/debug.go:3")],
       "calls": [call("GET", "/v1/users/{userId}", "r:client/users.go:20"),
                 call("GET", "/v1/users/{id}", "r:client/users.go:31")]}


def test_identical_runs_have_no_diff():
    assert not any(M.diff_runs(RUN, RUN, k) for k in M.KINDS)


def test_diff_reports_removed_added_and_resolution_changes():
    new = {**RUN, "endpoints": [ep("GET", "/v1/items/{itemId}", "r:api/items.go:10", None),   # same id, handler lost
                                ep("POST", "/v1/items", "r:api/items.go:11", "h2"),
                                ep("GET", "/metrics", "r:main.go:6")]}
    d = M.diff_runs(RUN, new, "endpoints")
    assert d.removed == [("ANY", "/health", "r:main.go:5"), ("GET", "/debug/vars", "r:internal/debug.go:3")]
    assert d.added == [("GET", "/metrics", "r:main.go:6")]
    assert d.resolution == [("GET", "/v1/items/{param}", "r:api/items.go:10")]


def test_score_matches_by_path_key_and_any():
    gab = {"endpoints": [{"method": "GET", "path": "/v1/items/:itemId"},       # express-style name, same key
                         {"method": "POST", "path": "/v1/items/"},
                         {"method": "GET", "path": "/health"}, {"method": "HEAD", "path": "/health"},   # ANY covers both
                         {"method": "DELETE", "path": "/v1/items/{id}"}]}
    s = M.score(RUN, gab, "endpoints")
    assert (s.extracted, s.expected) == (4, 5)
    assert s.false_positives == [("GET", "/debug/vars")]
    assert s.false_negatives == [("DELETE", "/v1/items/{param}")]
    assert s.precision == 3 / 4 and s.recall == 4 / 5


def test_miss_categories_come_from_the_expected_entries():
    gab = {"endpoints": [{"method": "DELETE", "path": "/v1/items/{id}", "category": "verb-alias"},
                         {"method": "PUT", "path": "/v1/items/{itemId}"},
                         {"method": "PUT", "path": "/v1/items/{id}", "category": "route-constraint-syntax"},
                         {"method": "GET", "path": "/health"}]}
    s = M.score(RUN, gab, "endpoints")
    assert M.miss_categories(gab, "endpoints", s) == {("DELETE", "/v1/items/{param}"): "verb-alias",
                                                      ("PUT", "/v1/items/{param}"): "route-constraint-syntax"}


def test_scope_limits_extracted_and_absent_kind_is_not_measured():
    gab = {"scope": ["api/"], "endpoints": [{"method": "GET", "path": "/v1/items/{id}"}, {"method": "POST", "path": "/v1/items"}]}
    s = M.score(RUN, gab, "endpoints")
    assert (s.precision, s.recall) == (1.0, 1.0)
    assert M.score(RUN, gab, "calls") is None


def test_scope_per_kind():
    gab = {"scope": {"endpoints": ["api/"], "calls": ["nowhere/"]},
           "endpoints": [{"method": "GET", "path": "/v1/items/{id}"}, {"method": "POST", "path": "/v1/items"}], "calls": []}
    assert M.score(RUN, gab, "endpoints").extracted == 2
    assert M.score(RUN, gab, "calls").extracted == 0


def test_calls_are_counted_as_distinct_pairs():
    s = M.score(RUN, {"calls": [{"method": "GET", "path": "/v1/users/{id}"}]}, "calls")
    assert (s.extracted, s.precision, s.recall) == (1, 1.0, 1.0)


def test_empty_expectation_makes_every_extracted_item_a_false_positive():
    s = M.score(RUN, {"calls": []}, "calls")
    assert s.precision == 0.0 and s.recall is None


def test_checked_precision_counts_verdicts_pending_and_stale():
    gab = {"checked": {"endpoints": [
        {"evidence": "r:api/items.go:10", "method": "GET", "path": "/v1/items/{id}", "ok": True},
        {"evidence": "r:internal/debug.go:3", "method": "GET", "path": "/debug/vars", "ok": False, "category": "debug-handler"},
        {"evidence": "r:old.go:1", "method": "GET", "path": "/gone", "ok": True},
        {"evidence": "r:main.go:5", "method": "ANY", "path": "/health", "ok": None}]}}
    c = M.checked_precision(RUN, gab, "endpoints")
    assert (c.ok, c.judged, c.pending) == (2, 3, 1)
    assert [i["path"] for i in c.stale] == ["/gone"]
    assert [i["category"] for i in c.wrong] == ["debug-handler"]
    assert M.checked_precision(RUN, gab, "calls") is None


def test_sample_is_reproducible_and_bounded():
    a = M.sample(RUN, "endpoints", 2, 7, "r")
    assert a == M.sample(RUN, "endpoints", 2, 7, "r")
    assert len(a) == 2 and all(i["ok"] is None for i in a)
    assert len(M.sample(RUN, "calls", 10, 7, "r")) == 2
    assert M.sample({}, "calls", 3, 7, "r") == []


def test_from_openapi_swagger2_base_path():
    spec = {"swagger": "2.0", "basePath": "/api/v1",
            "paths": {"/repos/{owner}/{repo}": {"get": {}, "delete": {}, "parameters": []}, "/version": {"get": {}}}}
    assert M.from_openapi(spec) == [{"method": "DELETE", "path": "/api/v1/repos/{owner}/{repo}"},
                                    {"method": "GET", "path": "/api/v1/repos/{owner}/{repo}"},
                                    {"method": "GET", "path": "/api/v1/version"}]


def test_from_openapi_v3_server_url_and_prefix_override():
    spec = {"openapi": "3.0.0", "servers": [{"url": "https://example.com/api/v3/"}],
            "paths": {"/pets/": {"post": {}, "summary": "x"}, "/pets/{petId}": {"$ref": "#/x", "put": {}}}}
    assert M.from_openapi(spec) == [{"method": "POST", "path": "/api/v3/pets"}, {"method": "PUT", "path": "/api/v3/pets/{petId}"}]
    assert M.from_openapi(spec, prefix="") == [{"method": "POST", "path": "/pets"}, {"method": "PUT", "path": "/pets/{petId}"}]
    assert M.openapi_prefix({"servers": [{"url": "/v2"}]}) == "/v2"


def test_from_openapi_follows_path_item_refs_to_other_files(tmp_path):
    (tmp_path / "write").mkdir()
    (tmp_path / "write" / "users.json").write_text('{"get": {}, "post": {}, "parameters": []}')
    spec = {"openapi": "3.0.0", "servers": [{"url": "/api/v3"}],
            "paths": {"/users/": {"$ref": "write/users.json"}, "/ping": {"$ref": "#/components/x"}}}
    assert M.from_openapi(spec, base=tmp_path) == [{"method": "GET", "path": "/api/v3/users"},
                                                   {"method": "POST", "path": "/api/v3/users"}]
