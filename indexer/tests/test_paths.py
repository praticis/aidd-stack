"""`core/paths.py` case by case: one named case per rule of `normalize_path`, and the pairs whose order matters, so a
changed or reordered regex fails a test that says which rule it was."""

import pytest

from aidd_indexer.core.paths import (expand_alternatives, has_literal_segment, is_url_literal, looks_like_rel_path,
                                     mask_placeholders, normalize_path, path_key, unquote)

NORMALIZE = [
    ("url-literal", "https://api.example.com/v1/users", "/v1/users"),
    ("url-literal-root", "https://api.example.com", "/"),
    ("express5-optional-group-dot", "/files{.:ext}", "/files.{ext}"),
    ("express5-optional-group-slash", "/users{/:id}", "/users/{id}"),
    ("express5-optional-wildcard", "/mcp{/*path}", "/mcp/{rest}"),
    ("hono-constraint", "/posts/:id{[0-9]+}", "/posts/{id}"),
    ("express-constraint", r"/items/:pk(\d+)", "/items/{pk}"),
    ("express-constraint-nested-parens", "/x/:pk(${UUID_REGEX})", "/x/{pk}"),
    ("typed-placeholder", "/users/{id:int}", "/users/{id}"),
    ("typed-placeholder-regex-braces", "/y/{id:[0-9]{4}}", "/y/{id}"),
    ("optional-placeholder", "/users/{id?}", "/users/{id}"),
    ("optional-typed-placeholder", "/users/{id:int?}", "/users/{id}"),
    ("optional-colon", "/chats/:roomid?", "/chats/{roomid}"),
    ("query-and-fragment", "/search?q=1#top", "/search"),
    ("sprintf-verbs", "/v1/users/%s/items/%d", "/v1/users/{param}/items/{param}"),
    ("js-template", "/v1/users/${id}", "/v1/users/{param}"),
    ("aspnet-catch-all", "/files/{*path}", "/files/{path}"),
    ("aspnet-catch-all-double", "/files/{**path}", "/files/{path}"),
    ("werkzeug-converter", "/u/<int:id>", "/u/{id}"),
    ("werkzeug-any", "/p/<any(a, b):page>", "/p/{page}"),
    ("werkzeug-plain", "/n/<name>", "/n/{name}"),
    ("colon-param", "/users/:id", "/users/{id}"),
    ("colon-param-after-dash", "/a-:b", "/a-{b}"),
    ("colon-param-after-dot", "/f.:ext", "/f.{ext}"),
    ("custom-verb-after-word", "/api/ai:transcribe", "/api/ai:transcribe"),
    ("custom-verb-after-placeholder", "/v1/{name}:cancel", "/v1/{name}:cancel"),
    ("spread-placeholder", "/x/{id...}", "/x/{id}"),
    ("string-format-index", "/api/items/{0}", "/api/items/{param}"),
    ("aspnet-tokens", "api/[controller]/[action]", "/api/{controller}/{action}"),
    ("aspnet-tokens-any-case", "api/[Controller]", "/api/{controller}"),
    ("wildcard-bare", "/static/*", "/static/{rest}"),
    ("wildcard-named", "/files/*filepath", "/files/{rest}"),
    ("leading-base-placeholder", "{base}/v1/users", "/v1/users"),
    ("double-slash", "/api//users", "/api/users"),
    ("trailing-slash", "/users/", "/users"),
    ("root", "/", "/"),
    ("leading-slash-added", "users/{id}", "/users/{id}"),
    # the order matters: a constraint or an optional marker may hold `?`, so each goes before the query is cut
    ("order-constraint-before-query", "/x/{id:regex(^a?b$)}", "/x/{id}"),
    ("order-optional-before-query", "/a/{id?}/b", "/a/{id}/b"),
    ("order-optional-colon-before-query", "/c/:id?/d", "/c/{id}/d"),
    # and the Express 5 group goes before the colon rule, which would read `{/:id}` as a placeholder inside braces
    ("order-group-before-colon", "/v{/:version}/x", "/v/{version}/x"),
]


@pytest.mark.parametrize("raw,expected", [c[1:] for c in NORMALIZE], ids=[c[0] for c in NORMALIZE])
def test_normalize_path(raw, expected):
    assert normalize_path(raw) == expected


@pytest.mark.parametrize("raw", [c[1] for c in NORMALIZE], ids=[c[0] for c in NORMALIZE])
def test_normalize_path_is_idempotent(raw):
    once = normalize_path(raw)
    assert normalize_path(once) == once


@pytest.mark.parametrize("raw,expected", [
    ("/users/{id:int?}", "/users/{p}"),
    ("/chats/:roomid?", "/chats/:roomid"),
    (r"/x/:pk(\d+)", "/x/:pk"),
    ("/u/<int:id>", "/u/{p}"),
], ids=["typed-optional", "optional-colon", "express-constraint", "werkzeug"])
def test_mask_placeholders(raw, expected):
    assert mask_placeholders(raw) == expected


def test_path_key_ignores_placeholder_names():
    assert path_key("/users/{id}/x/{name}") == "/users/{param}/x/{param}"
    assert path_key("/v1/users/{id}") == path_key("/v1/users/{userId}")


@pytest.mark.parametrize("raw,expected", [
    ("/{t:teams|channels}/x", ["/teams/x", "/channels/x"]),
    (r"/{ws:websocket(?:\/)?}", ["/websocket"]),
    ("/r/{sha}.{diffType:diff|patch}", ["/r/{sha}.{diffType:diff|patch}"]),
], ids=["alternatives", "word-with-optional-slash", "not-a-whole-segment"])
def test_expand_alternatives(raw, expected):
    assert expand_alternatives(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("https://host", True),
    ("https://host/v1/x?y=1", True),
    ("https://host/admin/{token}god_mode=true", False),
    ("/v1/x", False),
], ids=["host-only", "path-and-query", "not-a-route-path", "no-scheme"])
def test_is_url_literal(raw, expected):
    assert is_url_literal(raw) is expected


@pytest.mark.parametrize("raw,expected", [
    ('"abc"', "abc"), ("f'x'", "x"), ('$"a{b}"', "a{b}"), ('@"x"', "x"), ("`t`", "t"), ("abc", "abc"),
], ids=["double", "python-f", "csharp-interpolated", "csharp-verbatim", "backtick", "bare"])
def test_unquote(raw, expected):
    assert unquote(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("items/{id}", True), ("application/{id}", True), ("application/json", False), ("a/b.txt", False),
    ("https/x", False),
], ids=["relative-path", "mime-head-with-placeholder", "mime-type", "file-name", "scheme-head"])
def test_looks_like_rel_path(raw, expected):
    assert looks_like_rel_path(raw) is expected


@pytest.mark.parametrize("raw,expected", [
    ("/{param}/{param}/,", False), ("/v1/{param}", True), ("/", False),
], ids=["placeholders-and-comma", "named-segment", "root"])
def test_has_literal_segment(raw, expected):
    assert has_literal_segment(raw) is expected
