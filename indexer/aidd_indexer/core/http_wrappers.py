"""The app's own HTTP client wrappers: a function whose outbound call builds its path around one of its parameters
(`_http.GetAsync($"{_apiUrl}{uri}")` in `HttpGet(string uri)`, `self.session.get(self.base_url + path)` in
`_get(self, path)`), and the calls that give that parameter a literal (`HttpGet("catalog-items")`, `_get("/v1/x")`).
The scanners publish the first as facts and keep the second pending; each language composes them per repo."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from tree_sitter import Node

from ..languages.base import node_text as text
from .http_expr import valid_path
from .http_nodes import CONCAT_NODES, INTERPOLATION_NODES, STRING_NODES, STRING_TEXT_NODES, has_interpolation
from .paths import has_literal_segment, normalize_path, unquote

if TYPE_CHECKING:
    from .http_base import BaseScanner

Shape = tuple[int, str, str]          # (index of the parameter that is the path, text before it, text after it)


def param_shape(sc: "BaseScanner", a: Node, params: list[str]) -> Shape | None:
    """The shape of a path built around a parameter of the function, the first one: `uri`, `$"{_apiUrl}{uri}/{id}"`,
    `_base + uri`. A later parameter is a placeholder."""
    if a.type == "identifier":
        if text(a, sc.src) in params:
            return params.index(text(a, sc.src)), "", ""
        a = sc.resolve_local(a)
        if a is None:
            return None
    tokens = _tokens(sc, a, params)
    slots = [i for i, t in enumerate(tokens) if isinstance(t, int)]
    if not slots:
        return None
    i = slots[0]
    around = ("".join(t if isinstance(t, str) else "{param}" for t in tokens[:i]),
              "".join(t if isinstance(t, str) else "{param}" for t in tokens[i + 1:]))
    return tokens[i], *(re.sub(r"\{[^}]*\}", "{param}", x) for x in around)


def _tokens(sc: "BaseScanner", a: Node, params: list[str]) -> list[str | int]:
    """The pieces of an interpolated string or a concatenation: text, or the index of a parameter."""
    if a.type in STRING_NODES and (a.type == "interpolated_string_expression" or has_interpolation(a)):
        return [_piece(sc, c, params) for c in a.children if c.type in INTERPOLATION_NODES or c.type in STRING_TEXT_NODES]
    if a.type not in CONCAT_NODES:
        return []
    tokens: list[str | int] = []
    stack = [a]
    while stack:
        c = stack.pop()
        if c.type == a.type:
            stack.extend(reversed([k for k in c.children if k.is_named]))
        elif c.type == "identifier" and text(c, sc.src) in params:
            tokens.append(params.index(text(c, sc.src)))
        elif c.type in STRING_NODES and not has_interpolation(c):
            tokens.append(unquote(text(c, sc.src)))
        else:
            tokens.append(sc.path_of(c) or "{param}")
    return tokens


def _piece(sc: "BaseScanner", c: Node, params: list[str]) -> str | int:
    if c.type not in INTERPOLATION_NODES:
        return text(c, sc.src)
    inner = [k for k in c.children if k.is_named and k.type != "interpolation_brace"]
    name = text(inner[0], sc.src) if len(inner) == 1 and inner[0].type == "identifier" else None
    return params.index(name) if name in params else "{param}"


def wrapped_path(before: str, arg: str | None, after: str) -> tuple[str, str] | None:
    """(as written, normalized) path of a call that hands a wrapper `arg`, when the result names a segment."""
    raw = valid_path(before + arg + after, lenient=True) if arg else None
    path = normalize_path(raw) if raw else ""
    return (raw, path) if raw and has_literal_segment(path) else None
