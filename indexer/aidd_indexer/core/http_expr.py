"""From an expression to a path template — and to an HTTP method — for any parseable language.

`PathExpressions.path_of` reads literals, variables (`Scopes.binding`), the directory's constants
(`PackageContext.route_const`, filled by `collect_constants`), concatenation, templates (f"", $"", `${}`),
Sprintf/Format/format, Join/urljoin/Combine, Replace/Trim, `new Uri(...)`, request objects (`{url: ...}`) and
`x += e`. `method_from_args` reads the verb from literals, `http.MethodX` / `HttpMethod.X`, a `method` key or keyword,
or a local holding one. The scanner mixes this in (it needs `src`, `ctx` and `scopes`).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from tree_sitter import Node

from ..languages.base import node_text as text, walk
from .http_nodes import (APPEND_NODES, CALL_NODES, CONCAT_NODES, NAME_NODES, OBJECT_NODES, STRING_NODES,
                         STRING_TEXT_NODES, INTERPOLATION_NODES, WRAPPED_ARG_NODES, has_interpolation)
from .http_scope import in_function
from .paths import (ENV_URL_NAME, HTTP_METHODS, PATH_LITERAL, REL_PATH_LITERAL, URL_LITERAL, has_literal_segment,
                    looks_like_rel_path, mask_placeholders, normalize_path, unquote)

if TYPE_CHECKING:
    from .http_base import PackageContext

REQUEST_PATH_FIELDS = frozenset({"path", "url", "uri", "endpoint", "requesturi"})
PATH_NAME_NODES = NAME_NODES | {"property_identifier"}
PATH_CONCAT_NODES = CONCAT_NODES | {"concatenated_string"}
_ONE_WORD = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{2,}(\?.*)?$")          # `message`, `message?since=1`
_VERB_CONST = re.compile(r"^(?:http\.)?Method([A-Z][a-z]+)$|^HttpMethod\.([A-Z][a-z]+)$")


# -- the directory's constants ---------------------------------------------------------------
def collect_constants(fx, ctx: "PackageContext") -> None:
    """Module- and class-level constants holding a path or a base URL. A function's locals are not constants of the
    directory: a `url` parameter elsewhere would take the value of this function's `url` (`Scopes` reads them)."""
    src = fx.src
    for n in walk(fx.tree.root_node):
        name = val = None
        if n.type in ("const_spec", "var_spec", "variable_declarator"):           # Go, TS/JS, C#
            name, val = n.child_by_field_name("name"), n.child_by_field_name("value")
            if val is None and n.type == "variable_declarator":                    # C#: identifier + equals_value_clause
                kids = [c for c in n.children if c.is_named]
                if len(kids) >= 2:
                    name, val = kids[0], kids[-1]
        elif n.type == "assignment" and n.parent is not None and n.parent.type in ("module", "expression_statement"):  # Python
            name, val = n.child_by_field_name("left"), n.child_by_field_name("right")
        if name is not None and val is not None and name.type in ("identifier", "property_identifier") and not in_function(n):
            while val.type in ("expression_list", "equals_value_clause") and val.named_child_count == 1:
                val = val.named_children[0]
            parts = _concat_parts(val, src) if val.type in CONCAT_NODES else None
            if parts:
                ctx.const_parts[text(name, src)] = parts
            else:
                lit = first_string(val, src)
                if lit is not None and (PATH_LITERAL.match(lit) or REL_PATH_LITERAL.match(lit) or URL_LITERAL.match(lit)) and len(lit) > 1:
                    ctx.route_consts[text(name, src)] = lit
        if n.type in STRING_NODES:
            lit = unquote(text(n, src))
            if ENV_URL_NAME.match(lit):
                ctx.env_hints.add(lit)


def _concat_parts(n: Node, src: bytes) -> list[tuple[str, str | None]] | None:
    """`A + "/x" + B.C` → [("ref", "A"), ("lit", "/x"), ("ref", "C")]; None unless a `+` with a literal in it."""
    op = n.child_by_field_name("operator")
    if op is None or text(op, src) != "+":
        return None
    parts: list[tuple[str, str | None]] = []
    for c in (n.child_by_field_name("left"), n.child_by_field_name("right")):
        if c is None:
            return None
        if c.type == n.type:
            sub = _concat_parts(c, src)
            if sub is None:
                return None
            parts += sub
        elif c.type in STRING_NODES and not has_interpolation(c):
            parts.append(("lit", unquote(text(c, src))))
        elif c.type in NAME_NODES:
            parts.append(("ref", text(c, src).split(".")[-1]))
        else:
            parts.append(("unk", None))
    return parts if any(k == "lit" for k, _ in parts) else None


def first_string(n: Node, src: bytes) -> str | None:
    if n.type in STRING_NODES:
        return unquote(text(n, src))
    for c in n.children:
        if c.type in CALL_NODES:
            continue                       # don't mine literals out of calls (env("X"), t("key"))
        r = first_string(c, src)
        if r is not None:
            return r
    return None


def unwrap_arg(n: Node) -> Node:
    if n.type in WRAPPED_ARG_NODES:
        inner = [c for c in n.children if c.is_named]
        return inner[-1] if inner else n
    return n


# -- expressions ----------------------------------------------------------------------------
class PathExpressions:
    """Mixin for the scanners: needs `self.src`, `self.ctx` (PackageContext) and `self.scopes` (Scopes)."""

    def _unwrap_arg(self, n: Node) -> Node:
        return unwrap_arg(n)

    def path_of(self, n: Node, lenient: bool = False, _depth: int = 0) -> str | None:
        """Best-effort path template for an argument expression, or None when it is not path-like.
        `lenient` (outbound-call arguments): accept `items/{id}` style relative paths too."""
        if _depth > 4:
            return None
        t = n.type
        if t in STRING_NODES:
            return self._path_of_string(n, lenient, _depth)
        if t in PATH_NAME_NODES:
            return self._path_of_name(n, lenient, _depth)
        if t in PATH_CONCAT_NODES:
            return self._path_of_concat(n, lenient, _depth)
        if t in CALL_NODES:
            return self._path_of_call(n, lenient, _depth)
        if t in OBJECT_NODES:                                    # Request{Path: p} / {url: p}
            for key, val in self._keyed_fields(n):
                if key.lower() in REQUEST_PATH_FIELDS:
                    return self.path_of(val, True, _depth + 1)
            return None
        if t == "object_creation_expression":                   # new Uri("api/x", UriKind.Relative)
            if "Uri" not in text(n, self.src).split("(")[0]:
                return None
            args = next((c for c in n.children if c.type == "argument_list"), None)
            arg_nodes = [unwrap_arg(c) for c in args.children if c.is_named] if args else []
            return self.path_of(arg_nodes[0], lenient, _depth + 1) if arg_nodes else None
        if t in APPEND_NODES:
            return self._path_of_append(n, lenient, _depth)
        if t in ("parenthesized_expression", "await_expression", "unary_expression"):
            inner = [c for c in n.children if c.is_named]
            return self.path_of(inner[0], lenient, _depth + 1) if inner else None
        if t in ("argument", "keyword_argument"):
            inner = [c for c in n.children if c.is_named]
            return self.path_of(inner[-1], lenient, _depth + 1) if inner else None
        return None

    def _string_text(self, n: Node, lenient: bool, _depth: int) -> str:
        """A string literal's text, with the template's substitutions read by `_interpolated`."""
        return self._interpolated(n, lenient, _depth) if has_interpolation(n) else unquote(text(n, self.src))

    def _path_of_string(self, n: Node, lenient: bool, _depth: int) -> str | None:
        lit = self._interpolated(n, lenient, _depth) if has_interpolation(n) or n.type == "interpolated_string_expression" \
            else unquote(text(n, self.src))
        lit = re.sub(r"\$\{[^}]*\}", "{param}", lit)
        m = re.match(r"^\{param\}(/?)(.*)$", lit)              # leading base-URL placeholder
        if m:
            rest = m.group(2)
            if m.group(1) == "/" or (lenient and (looks_like_rel_path(rest) or _ONE_WORD.match(rest))):
                lit = "/" + rest.lstrip("/")
            else:
                return None
        check = mask_placeholders(lit).split("?", 1)[0].split("#", 1)[0]    # `items/{id}?api-version=2.0`: the query is not the path
        if URL_LITERAL.match(lit) or PATH_LITERAL.match(check) or REL_PATH_LITERAL.match(lit):
            return lit if len(check) > 1 else None
        if lenient and looks_like_rel_path(check):
            return "/" + lit
        return None

    def _path_of_name(self, n: Node, lenient: bool, _depth: int) -> str | None:
        """A local binding first (a parameter has no value here), then the directory's constants."""
        if n.type == "identifier":
            bound, val = self.scopes.binding(n)
            if bound:
                return self.path_of(val, lenient, _depth + 1) if val is not None else None
        return self.ctx.route_const(text(n, self.src).split(".")[-1])

    def _path_of_concat(self, n: Node, lenient: bool, _depth: int) -> str | None:
        """`base + "/v1/x" + id`; an unknown first operand is a base URL."""
        t = n.type
        operands: list[Node] = []                    # flatten `a + b + c + ...` (left-nested) into one list
        stack = [c for c in reversed(n.children) if c.is_named]
        while stack:
            c = stack.pop()
            if c.type == t:
                stack.extend(k for k in reversed(c.children) if k.is_named)
            else:
                operands.append(c)
        raw, lead = "", False
        for c in operands:
            verb = re.match(r"^(?:http\.)?Method([A-Z][a-z]+)$", text(c, self.src))        # http.MethodPut + " " + path
            if verb and verb.group(1).upper() in HTTP_METHODS:
                raw += verb.group(1).upper()
                continue
            p = self._string_text(c, lenient, _depth + 1) if c.type in STRING_NODES else self.path_of(c, lenient, _depth + 1)
            if p is None:
                if raw:
                    raw += "{param}"
                else:
                    lead = True
                continue
            raw += p
        raw = re.sub(r"^\{param\}(?=/)", "", raw)
        if not raw:
            return None
        if raw.startswith("/") or URL_LITERAL.match(raw) or REL_PATH_LITERAL.match(raw) or re.match(r"^[A-Z]+ /", raw):
            return raw                                           # "PUT " + base + "/x" is a net/http 1.22 pattern
        if lenient and lead and _ONE_WORD.match(raw):
            return "/" + raw                                     # base + 'message' (gotify)
        return ("/" + raw) if lenient and "/" in raw and not raw.startswith("{") else None

    def _path_of_call(self, n: Node, lenient: bool, _depth: int) -> str | None:
        """fmt.Sprintf("/v1/%s", id), "...".format(x), path.Join, urljoin, Combine, Replace/Trim on a path."""
        fn = n.child_by_field_name("function")
        args = n.child_by_field_name("arguments")
        if fn is None:      # C#: invocation_expression children = [member_access|identifier, argument_list]
            kids = [c for c in n.children if c.is_named]
            fn, args = (kids[0] if kids else None), next((c for c in kids if c.type == "argument_list"), None)
        fname = text(fn, self.src).split(".")[-1] if fn is not None else ""
        if args is None:
            return None
        arg_nodes = [unwrap_arg(c) for c in args.children if c.is_named]
        if fname in ("Sprintf", "Errorf", "Format", "format"):
            if fname == "format" and fn is not None and fn.type == "attribute":      # "/v1/{}".format(x)
                recv = fn.child_by_field_name("object")
                rp = self.path_of(recv, lenient, _depth + 1) if recv is not None else None
                return rp.replace("{}", "{param}") if rp else None
            return self.path_of(arg_nodes[0], lenient, _depth + 1) if arg_nodes else None
        if fname in ("Replace", "replace", "TrimStart", "TrimEnd", "Trim", "ToLower", "ToLowerInvariant", "lstrip", "rstrip", "strip"):
            recv = fn.child_by_field_name("object") if fn is not None and fn.type == "attribute" else None
            if recv is None and fn is not None and fn.type in ("member_access_expression", "member_expression", "selector_expression"):
                kids_fn = [c for c in fn.children if c.is_named]
                recv = kids_fn[0] if kids_fn else None
            return self.path_of(recv, lenient, _depth + 1) if recv is not None else None
        if fname in ("Join", "JoinPath", "urljoin", "Combine"):
            segs = [(unquote(text(a, self.src)) if a.type in STRING_NODES and not has_interpolation(a)
                     else self.path_of(a, lenient, _depth + 1)) or "{param}" for a in arg_nodes]
            segs = [s for s in segs if s]
            return ("/" + "/".join(s.strip("/") for s in segs)) if segs else None
        return None

    def _path_of_append(self, n: Node, lenient: bool, _depth: int) -> str | None:
        """`url += "/" + id`: the earlier value plus the tail. With the base unknown (a URL from a call) the tail is
        what we know — if it names a segment: `path += "/"` onto a parameter is no route (chi FileServer)."""
        left, right = n.child_by_field_name("left"), n.child_by_field_name("right")
        if left is None or right is None or not self.scopes.appends_to(n, text(left, self.src)):
            return None
        left, right = (x.named_children[0] if x.type == "expression_list" and x.named_child_count == 1 else x for x in (left, right))
        base = self.path_of(left, lenient, _depth + 1)
        tail = self.path_of(right, lenient, _depth + 1) if right.type not in STRING_NODES else unquote(text(right, self.src))
        if base is None:
            ok = tail is not None and tail.startswith("/") and has_literal_segment(normalize_path(tail))
            return tail if ok else None
        return base + (tail if tail is not None else "{param}")

    def _interpolated(self, n: Node, lenient: bool = False, _depth: int = 0) -> str:
        """Template text with each substitution as `{param}` — except a local variable holding a path, read as in a
        concatenation (`url = `${url}?notify=true``). A module constant stays a placeholder: in a generic wrapper
        (`${prefix}/${API_PATH}${path}`) it would make a path out of what is only a base."""
        parts = []
        for c in n.children:
            if c.type in INTERPOLATION_NODES:
                inner = [k for k in c.children if k.is_named]
                v = None
                if len(inner) == 1 and inner[0].type == "identifier":
                    bound, val = self.scopes.binding(inner[0])
                    v = self.path_of(val, lenient, _depth + 1) if bound and val is not None else None
                parts.append(v if v is not None else "{param}")
            elif c.type in STRING_TEXT_NODES:
                parts.append(text(c, self.src))
            # interpolation_start ($"), string_start/end, quotes: structural, no text
        raw = "".join(parts) if parts else unquote(text(n, self.src))
        return re.sub(r"\{[^}]*\}", "{param}", raw) if n.type == "interpolated_string_expression" else raw

    def _keyed_fields(self, n: Node) -> list[tuple[str, Node]]:
        """(key, value) pairs of an object / struct literal, one level deep."""
        out: list[tuple[str, Node]] = []
        for d in walk(n):
            if d is n or d.type not in ("keyed_element", "pair", "member_declarator", "property_assignment"):
                continue
            kids = [c for c in d.children if c.is_named]
            if len(kids) >= 2:
                val = kids[-1]
                while val.type == "literal_element" and val.named_child_count == 1:     # Go wraps both sides
                    val = val.named_children[0]
                out.append((unquote(text(kids[0], self.src)).strip(), val))
        return out

    # -- the HTTP method ------------------------------------------------------------------------
    def method_from_args(self, arg_nodes: list[Node]) -> str | None:
        for a in arg_nodes:                                  # request(method="POST", url=...)
            nm = a.child_by_field_name("name") if a.type == "keyword_argument" else None
            if nm is not None and text(nm, self.src) == "method":
                v = self._method_value(a.child_by_field_name("value"))
                if v:
                    return v
        for a in arg_nodes[:4]:
            txt = text(a, self.src)
            if a.type in STRING_NODES and unquote(txt).upper() in HTTP_METHODS:
                return unquote(txt).upper()
            m = re.match(r"^(?:http\.)?(?:HttpMethod\.)?Method([A-Z][a-z]+)$|^HttpMethod\.([A-Z][a-z]+)$", txt)
            if m:
                v = (m.group(1) or m.group(2) or "").upper()
                if v in HTTP_METHODS:
                    return v
            if a.type in OBJECT_NODES:
                mm = re.search(r"method\s*[:=]\s*(?:[\"'`]([A-Za-z]+)[\"'`]|(?:http\.)?Method([A-Z][a-z]+)|HttpMethod\.([A-Z][a-z]+))", txt, re.I)
                if mm:
                    v = (mm.group(1) or mm.group(2) or mm.group(3) or "").upper()
                    if v in HTTP_METHODS:
                        return v
                for key, val in self._keyed_fields(a):         # {method: method}, the verb in a local
                    if key == "method":
                        v = self._method_value(val)
                        if v:
                            return v
                for c in a.children:                          # {method}
                    if c.type == "shorthand_property_identifier" and text(c, self.src) == "method":
                        v = self._method_value(c)
                        if v:
                            return v
        return None

    def _method_value(self, n: Node | None, depth: int = 0) -> str | None:
        """The HTTP verb an expression holds: a literal, `http.MethodPost` / `HttpMethod.Post`, or a local holding one."""
        if n is None or depth > 2:
            return None
        txt = text(n, self.src)
        if n.type in STRING_NODES:
            v = unquote(txt).upper()
            return v if v in HTTP_METHODS else None
        m = _VERB_CONST.match(txt)
        if m:
            v = (m.group(1) or m.group(2) or "").upper()
            return v if v in HTTP_METHODS else None
        if n.type in ("identifier", "shorthand_property_identifier"):
            return self._method_value(self.scopes.binding(n)[1], depth + 1)
        return None
