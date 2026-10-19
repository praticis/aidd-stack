"""TS/JS facts of a package that the HTTP scanner reads across files: the module's clients with a base
(`PackageContext.client_bases`), the classes whose field holds it, the interceptors that rewrite a request's url, and
the string members of an enum."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from tree_sitter import Node

from ...core.http_expr import SEGMENT, concat_parts, first_string, template_parts
from ...core.http_nodes import CONCAT_NODES, STRING_NODES, has_interpolation
from ...core.http_scope import in_function
from ...core.paths import PATH_LITERAL, REL_PATH_LITERAL, unquote
from ...tree import node_text as text, walk

if TYPE_CHECKING:
    from ...core.http_base import PackageContext


def package_facts_reader(src: bytes) -> Callable[[Node, bytes, "PackageContext", str], bool]:
    """The reader for one file. An interceptor is looked for only in a file that names one."""
    nodes = TS_CLIENT_NODES if b".interceptors." in src else TS_CLIENT_NODES - {"call_expression"}

    def read(n: Node, src: bytes, ctx: "PackageContext", path: str) -> bool:
        t = n.type
        if t in nodes:                                           # a client with a base (`client_bases`)
            _client_node(n, src, ctx, path)
        if t == "enum_assignment":                                # enum RouteKey { Asset = 'assets' }
            _enum_member(n, src, ctx)
            return True
        return False

    return read


def _client_node(n: Node, src: bytes, ctx: "PackageContext", path: str) -> None:
    t = n.type
    if t == "variable_declarator":
        _ts_client(n, src, ctx, path)
    elif t == "call_expression":
        _ts_interceptor(n, src, ctx, path)
    elif t == "export_statement":
        v = n.child_by_field_name("value")
        if v is not None and v.type == "identifier" and any(c.type == "default" for c in n.children):
            ctx.client_bases.setdefault((path, "default"), ("alias", text(v, src)))
    else:
        _ts_client_class(n, src, ctx)


def _enum_member(n: Node, src: bytes, ctx: "PackageContext") -> None:
    """A string member of a TS enum, known only as `Enum.Member` (immich `@Controller(RouteKey.Asset)`)."""
    decl = n.parent.parent if n.parent is not None else None
    enum = decl.child_by_field_name("name") if decl is not None and decl.type == "enum_declaration" else None
    kids = [c for c in n.children if c.is_named]
    if enum is None or len(kids) != 2 or kids[1].type not in STRING_NODES or has_interpolation(kids[1]):
        return
    name, lit = f"{text(enum, src)}.{text(kids[0], src)}", first_string(kids[1], src)
    if lit is not None and len(lit) > 1 and (PATH_LITERAL.match(lit) or REL_PATH_LITERAL.match(lit)):
        ctx.define(name, raw=lit)
    elif lit is not None and SEGMENT.match(lit):
        ctx.define(name, segment=lit)


CLIENT_BASE_KEYS = frozenset({"baseURL", "baseUrl", "prefixUrl"})   # axios, ofetch / a class's field, ky and got
TS_CLIENT_NODES = frozenset({"variable_declarator", "call_expression", "export_statement", "class_declaration", "class"})
CLIENT_FACTORIES = frozenset({"create", "extend"})                   # axios.create({..}), ky.extend({..})


def _ts_client(n: Node, src: bytes, ctx: "PackageContext", path: str) -> None:
    """A module's client with a base (`PackageContext.client_bases`): `const api = axios.create({ baseURL: "/api" })`
    (docmost), `ky.extend({ prefixUrl })`; `export const client = new ApiClient({ baseUrl: .. })`, whose class says
    which option gives its base (`_ts_client_class`)."""
    name, val = n.child_by_field_name("name"), n.child_by_field_name("value")
    while val is not None and val.type in ("await_expression", "as_expression", "parenthesized_expression",
                                           "non_null_expression", "satisfies_expression") and val.named_child_count:
        val = val.named_children[0]
    if name is None or val is None or name.type != "identifier" or val.type not in ("call_expression", "new_expression") \
            or in_function(n):
        return
    args = val.child_by_field_name("arguments")
    obj = next((a for a in args.named_children if a.type == "object"), None) if args is not None else None
    given = {k: parts for k, v in _object_pairs(obj, src) if k in CLIENT_BASE_KEYS and (parts := _base_parts(v, src))}
    if val.type == "new_expression":
        ctor = val.child_by_field_name("constructor")
        if ctor is not None and ctor.type == "identifier":
            ctx.client_bases[(path, text(name, src))] = ("new", text(ctor, src), given)
        return
    fn = val.child_by_field_name("function")
    prop = fn.child_by_field_name("property") if fn is not None and fn.type == "member_expression" else None
    if prop is not None and text(prop, src) in CLIENT_FACTORIES and given:
        ctx.client_bases[(path, text(name, src))] = ("parts", next(iter(given.values())))



def _ts_interceptor(n: Node, src: bytes, ctx: "PackageContext", path: str) -> None:
    """`api.interceptors.request.use(config => { config.url = `${org}${config.url}` })` (dispatch): the request's url
    or base is rewritten at runtime, so the client's base is not all that goes before a path — none is applied."""
    fn, args = n.child_by_field_name("function"), n.child_by_field_name("arguments")
    m = re.fullmatch(r"([A-Za-z_$][\w$]*)\.interceptors\.request\.use", text(fn, src)) if fn is not None else None
    if m is None or args is None or in_function(n):
        return
    for a in walk(args):
        left = a.child_by_field_name("left") if a.type in ("assignment_expression", "augmented_assignment_expression") else None
        if left is not None and re.search(r"\.(url|baseURL)$", text(left, src)):
            ctx.client_rewritten.add((path, m.group(1)))
            return

def _ts_client_class(n: Node, src: bytes, ctx: "PackageContext") -> None:
    """A class whose base is a field: `baseUrl = "/api"`, or the constructor's `this.baseUrl = options.baseUrl ||
    "/api"` (outline's ApiClient) — the option that gives it (`baseUrl`) and its default."""
    cname, body = n.child_by_field_name("name"), n.child_by_field_name("body")
    if cname is None or body is None:
        return
    found: tuple[str | None, list] | None = None
    for m in body.named_children:
        key = m.child_by_field_name("name") or m.child_by_field_name("property")
        if m.type in ("public_field_definition", "field_definition") and key is not None \
                and text(key, src) in CLIENT_BASE_KEYS and (parts := _base_parts(m.child_by_field_name("value"), src)):
            found = (None, parts)
        if m.type == "method_definition" and key is not None and text(key, src) == "constructor":
            for a in walk(m):
                left, right = a.child_by_field_name("left"), a.child_by_field_name("right")
                if a.type != "assignment_expression" or left is None or right is None \
                        or not re.fullmatch(r"this\.(baseURL|baseUrl|prefixUrl)", text(left, src)):
                    continue
                option = None
                if right.type == "binary_expression" and text(right.child_by_field_name("operator"), src) in ("||", "??"):
                    given = right.child_by_field_name("left")
                    option = text(given.child_by_field_name("property"), src) \
                        if given is not None and given.type == "member_expression" else None
                    right = right.child_by_field_name("right")
                parts = _base_parts(right, src)
                if parts:
                    found = (option, parts)
    if found is not None:
        nm = text(cname, src)
        ctx.client_classes[nm] = found if ctx.client_classes.get(nm, found) == found else None


def _object_pairs(obj: Node | None, src: bytes) -> list[tuple[str, Node]]:
    """(key, value) of an object literal's own pairs."""
    out = []
    for d in obj.named_children if obj is not None else ():
        key, value = d.child_by_field_name("key"), d.child_by_field_name("value")
        if d.type == "pair" and key is not None and value is not None:
            out.append((unquote(text(key, src)), value))
    return out


def _base_parts(v: Node | None, src: bytes) -> list[tuple[str, str | None]] | None:
    """A base as `PackageContext._joined` reads it: a literal, a constant, `A + "/x"`, `` `${A}/x` ``."""
    if v is None:
        return None
    if v.type in STRING_NODES and not has_interpolation(v):
        lit = first_string(v, src)
        return [("lit", lit)] if lit else None
    if v.type == "template_string":
        return template_parts(v, src)
    if v.type in CONCAT_NODES:
        return concat_parts(v, src)
    return [("ref", text(v, src))] if v.type in ("identifier", "member_expression") else None
