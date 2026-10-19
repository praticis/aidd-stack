"""`core/matching.py`: the rule the linker, the MCP and the corpus scorer share."""

import pytest

from aidd_indexer.core.matching import compared, is_segment_suffix, methods_compatible, query_key


@pytest.mark.parametrize("asked,key", [
    ("/v1/users/{id}", "/v1/users/{param}"),
    ("/v1/users/{userId}/", "/v1/users/{param}"),
    ("/users/:id", "/users/{param}"),
    ("api/accounts/{id}/details", "/api/accounts/{param}/details"),
    ("https://host/v1/x?y=1", "/v1/x"),
    ("/", "/"),
], ids=["template", "trailing-slash", "express-param", "no-leading-slash", "url-and-query", "root"])
def test_query_key(asked, key):
    assert query_key(asked) == key


def test_aspnet_routes_compare_without_case():
    assert compared("/api/Accounts/{param}", "aspnet") == "/api/accounts/{param}"
    assert compared("/api/Accounts/{param}", "gin") == "/api/Accounts/{param}"
    assert compared("/x", None) == "/x"


def test_methods_meet_when_equal_or_any():
    assert methods_compatible("GET", "GET") and methods_compatible("ANY", "POST") and methods_compatible("PUT", "ANY")
    assert not methods_compatible("GET", "POST")


def test_segment_suffix():
    assert is_segment_suffix("/v1/x/{param}", "/api/v1/x/{param}")
    assert not is_segment_suffix("/v1/x", "/v1/x")
