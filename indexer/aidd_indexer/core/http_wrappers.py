"""The app's own HTTP client wrappers: a function whose outbound call builds its path around one of its parameters
(`_http.GetAsync($"{_apiUrl}{uri}")` in `HttpGet(string uri)`, `self.session.get(self.base_url + path)` in
`_get(self, path)`), and the calls that give that parameter a literal (`HttpGet("catalog-items")`, `_get("/v1/x")`).
The scanners publish the first as facts and keep the second pending; `compose_wrapped_calls` resolves them per repo."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING

from tree_sitter import Node

from ..languages.base import node_text as text
from .http_expr import valid_path
from .http_nodes import CONCAT_NODES, INTERPOLATION_NODES, STRING_NODES, STRING_TEXT_NODES, has_interpolation
from .paths import HTTP_METHODS, has_literal_segment, normalize_path, unquote

if TYPE_CHECKING:
    from .http_base import BaseScanner, HttpResult, Pending

Shape = tuple[int, str, str]          # (index of the parameter that is the path, text before it, text after it)
PARAM = "param"                       # an argument built around a parameter of the caller: (PARAM, *Shape)
FIELDS = "fields"                     # an object literal argument: (FIELDS, ((key, value), ..))
UNKNOWN = ("unknown",)                # an argument the scanner cannot read: not the same as no argument


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
    """The pieces of an interpolated string or a concatenation: text, or the index of a parameter. A query string
    glued to the end (`endpoint + (vars ? '?' + qs(vars) : '')`) is not part of the path."""
    if a.type in STRING_NODES and (a.type == "interpolated_string_expression" or has_interpolation(a)):
        pieces = [c for c in a.children if c.type in INTERPOLATION_NODES or c.type in STRING_TEXT_NODES]
        tokens = [_piece(sc, c, params) for c in pieces]
        last = _inner(pieces[-1]) if pieces and pieces[-1].type in INTERPOLATION_NODES else None
    elif a.type in CONCAT_NODES:
        operands = _operands(a)
        tokens = [_operand(sc, c, params) for c in operands]
        last = operands[-1]
    else:
        return []
    if len(tokens) > 1 and not isinstance(tokens[-1], int) and _glued(tokens[-2]) and sc.query_tail(last):
        return tokens[:-1]
    return tokens


def _operands(a: Node) -> list[Node]:
    """`a + b + c`, left-nested, as one list."""
    out, stack = [], [a]
    while stack:
        c = stack.pop()
        if c.type == a.type:
            stack.extend(reversed([k for k in c.children if k.is_named]))
        else:
            out.append(c)
    return out


def _operand(sc: "BaseScanner", c: Node, params: list[str]) -> str | int:
    if c.type == "identifier" and text(c, sc.src) in params:
        return params.index(text(c, sc.src))
    if c.type in STRING_NODES and not has_interpolation(c):
        return unquote(text(c, sc.src))
    return sc.path_of(c) or "{param}"


def _inner(c: Node) -> Node | None:
    inner = [k for k in c.children if k.is_named and k.type != "interpolation_brace"]
    return inner[0] if len(inner) == 1 else None


def _glued(t: str | int) -> bool:
    """A parameter, or text that ends in a word or a placeholder: what follows with no separator is not a new
    segment."""
    return isinstance(t, int) or bool(t) and (t[-1].isalnum() or t[-1] == "}")


def _piece(sc: "BaseScanner", c: Node, params: list[str]) -> str | int:
    if c.type not in INTERPOLATION_NODES:
        return text(c, sc.src)
    inner = _inner(c)
    name = text(inner, sc.src) if inner is not None and inner.type == "identifier" else None
    if name in params:
        return params.index(name)
    return (sc.path_of(inner) if inner is not None else None) or "{param}"      # `${BASE}`, `${apiRoot()}`


def wrapped_path(before: str, arg: str | None, after: str) -> tuple[str, str] | None:
    """(as written, normalized) path of a call that hands a wrapper `arg`, when the result names a segment."""
    raw = valid_path(before + arg + after, lenient=True) if arg else None
    path = normalize_path(raw) if raw else ""
    return (raw, path) if raw and has_literal_segment(path) else None


def continues_path(shape: Shape) -> bool:
    """A parameter right after a word or a placeholder of the path (`"/api/v1" + url`, `${base}${path}`) is the rest of
    the path, so the function around it is a wrapper; after a slash, `.`, `-` or `=` it is part of one segment
    (`/users/${id}`, `/users.${action}`)."""
    return bool(shape[1]) and _glued(shape[1])


# -- composing: a wrapper fact is (path index, before, after, verb, verb index, parameters, the verb's default); the
# verb index is a parameter's, or (parameter, key) for an option object's field (`{ method = "GET" }`).
def compose_wrapped_calls(out: "HttpResult", rule: str, bases_rule: str) -> list["Pending"]:
    """The pending `rule` calls to the repo's client wrappers, as outbound calls. A call that hands a wrapper a
    parameter of its own function makes that function a wrapper, so a chain of wrappers resolves in a few rounds.
    Returns the calls whose target is a wrapper."""
    facts: dict[str, set[tuple]] = {k: set(v) for k, v in out.facts.get(rule, {}).items()}
    bases = out.facts.get(bases_rule, {})
    waiting = [p for p in out.pending if p.rule == rule]
    done: list["Pending"] = []
    for _ in range(4):
        rest = [p for p in waiting if not _resolve(p, facts, bases, out)]
        kept = {id(p) for p in rest}
        done += [p for p in waiting if id(p) not in kept]
        if len(rest) == len(waiting):
            break
        waiting = rest
    return done


def _resolve(p: "Pending", facts: dict[str, set[tuple]], bases: dict, out: "HttpResult") -> bool:
    """Record the call `p`, or make its function a wrapper; False while its target is not a known wrapper."""
    target, values, named, outer, outer_params = p.key
    shape = _shape(facts, bases, target)
    if shape is None:
        return False
    idx, before, after, _, _, params, default = shape
    path = _arg(values, named, params, idx)
    verb, vi_out = _call_verb(values, named, shape)
    if _param_of(path, whole=False) is not None:
        if outer is not None:
            _, i, b, a = path
            kept = default if isinstance(vi_out, tuple) else None
            facts.setdefault(outer, set()).add((i, before + b, a + after, verb, vi_out, outer_params, kept))
        return True
    found = wrapped_path(before, path, after) if isinstance(path, str) else None
    if found is not None:
        out.calls.append(replace(p.item, method=verb or "ANY", path=found[1], raw_path=found[0]))
    return True


def _call_verb(values: tuple, named: tuple, shape: tuple) -> tuple[str | None, int | tuple | None]:
    """The verb a call to a wrapper sends, or where its own function takes the verb from. The wrapper's default only
    when the call gives nothing there: options it cannot read leave the verb unknown."""
    _, _, _, verb, vi, params, default = shape
    if verb is not None:
        return verb, None
    how = _arg(values, named, params, vi)
    vi_out = _param_of(how)
    if vi_out is None and isinstance(vi, tuple) and how is None:
        given = _arg(values, named, params, vi[0])                      # the options handed on: `fetch(url, options)`
        whole = _param_of(given)
        vi_out = (whole, vi[1]) if whole is not None else None
        how = UNKNOWN if given == UNKNOWN else None
    return verb_of(how) or (default if vi_out is None and how != UNKNOWN else None), vi_out


def _shape(facts: dict[str, set[tuple]], bases: dict, target: tuple) -> tuple | None:
    """The one shape of the wrapper a call names: a function's, or the method of the class or of its nearest base
    that defines it. Two different shapes under one name give nothing."""
    if target[0] == "func":
        found = facts.get(target[1])
        return next(iter(found)) if found and len(found) == 1 else None
    _, cls, method = target
    level = [cls]
    for _ in range(5):
        found = next((facts[k] for c in level if (k := f"{c}.{method}") in facts), None)
        if found is not None:
            return next(iter(found)) if len(found) == 1 else None
        level = [b for c in level for names in bases.get(c, ()) for b in names]
    return None


def _arg(values: tuple, named: tuple, params: tuple, i: int | tuple | None) -> str | tuple | None:
    if isinstance(i, tuple):
        obj = _arg(values, named, params, i[0])
        return dict(obj[1]).get(i[1]) if isinstance(obj, tuple) and obj[0] == FIELDS else None
    if i is None:
        return None
    if i < len(values):
        return values[i]
    return dict(named).get(params[i]) if i < len(params) else None


def verb_of(how: str | tuple | None) -> str | None:
    return how.upper() if isinstance(how, str) and how.upper() in HTTP_METHODS else None


def _param_of(how: str | tuple | None, whole: bool = True) -> int | None:
    """The caller's parameter an argument is: as it is, or (`whole=False`) with text around it."""
    if not isinstance(how, tuple) or how[0] != PARAM:
        return None
    return how[1] if not whole or how[2] == "" and how[3] == "" else None
