"""From an expression to a path template — and to an HTTP method — for any parseable language.

`PathExpressions.path_of` reads literals, variables (`Scopes.binding`), the directory's constants
(`PackageContext.route_const`, filled by `collect_constants`), concatenation, templates (f"", $"", `${}`),
Sprintf/Format/format, Join/urljoin/Combine, Replace/Trim, `new Uri(...)`, request objects (`{url: ...}`), `x += e`,
Go's `url.URL` (`u.Path = e`, `u.Path += e`, then `u.String()` or `u`) and grpc-gateway's `runtime.NewPattern`.
`method_from_args` reads the verb from literals, `http.MethodX` / `HttpMethod.X`, a `method` key or keyword, or a local
holding one. The scanner mixes this in (it needs `src`, `ctx`, `scopes` and a `_path_memo` dict).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from tree_sitter import Node

from ..languages.base import node_text as text, walk
from .http_nodes import (APPEND_NODES, CALL_NODES, CLASS_NODES, CONCAT_NODES, NAME_NODES, OBJECT_NODES, STRING_NODES,
                         STRING_TEXT_NODES, INTERPOLATION_NODES, WRAPPED_ARG_NODES, has_interpolation)
from .http_scope import END, in_function
from .paths import (ENV_URL_NAME, HTTP_METHODS, PATH_LITERAL, REL_PATH_LITERAL, has_literal_segment, is_url_literal,
                    looks_like_rel_path, mask_placeholders, normalize_path, unquote)

if TYPE_CHECKING:
    from .http_base import PackageContext

REQUEST_PATH_FIELDS = frozenset({"path", "url", "uri", "endpoint", "requesturi"})
PATH_NAME_NODES = NAME_NODES | {"property_identifier"}
PATH_CONCAT_NODES = CONCAT_NODES | {"concatenated_string"}
_ONE_WORD = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{2,}(\?.*)?$")          # `message`, `message?since=1`
_PATH_NAMED = re.compile(r"^(path|url|uri|endpoint|route|href|target|location|\w*(Path|Url|Uri|_path|_url|_uri))$", re.I)
_JOIN_CALL = re.compile(r"^(Join|JoinPath|AppendPaths?|urljoin|Combine(Uri|Url|Path|Paths)?|UrlCombine)$")   # path.Join, urljoin, CombineUri
_SEGMENT = re.compile(r"^[A-Za-z][A-Za-z0-9_.\-]{1,63}$")                  # `cases`, `signal_instances`, `v2`
_VERB_CONST = re.compile(r"^(?:http\.)?Method([A-Z][a-z]+)$|^HttpMethod\.([A-Z][a-z]+)$")


def grpc_gateway_pattern(ops: list[int], pool: list[str], verb: str = "") -> str | None:
    """The path a grpc-gateway `runtime.NewPattern(1, ops, pool, verb)` matches: `ops` is a stack program of (opcode,
    operand) pairs — 1 push a segment, 2 push the literal `pool[operand]`, 3 push the rest of the path, 4 join the
    top `operand` items, 5 capture the top as the variable `pool[operand]`, 0 nothing."""
    stack: list[str] = []
    for i in range(0, len(ops) - 1, 2):
        op, arg = ops[i], ops[i + 1]
        if op == 1:
            stack.append("*")
        elif op == 2 and arg < len(pool):
            stack.append(pool[arg])
        elif op == 3:
            stack.append("**")
        elif op == 4 and 0 < arg <= len(stack):
            stack[-arg:] = ["/".join(stack[-arg:])]
        elif op == 5 and stack and arg < len(pool):
            stack[-1] = "{" + pool[arg] + "}"
        elif op != 0:
            return None
    return ("/" + "/".join(stack) + (":" + verb if verb else "")) if stack else None


# -- the directory's constants ---------------------------------------------------------------
def owner_class(n: Node, src: bytes) -> str | None:
    """Name of the class (struct, record) `n` is declared in."""
    p = n.parent
    while p is not None and p.type not in CLASS_NODES:
        p = p.parent
    name = p.child_by_field_name("name") if p is not None else None
    return text(name, src) if name is not None else None


def collect_constants(fx, ctx: "PackageContext") -> None:
    """Module- and class-level constants holding a path or a base URL — or a single word, a path segment only where a
    template puts it whole (`/${resource}/${id}`). A function's locals are not constants of the directory: a `url`
    parameter elsewhere would take the value of this function's `url` (`Scopes` reads them). A class-level one is
    also known by `Class.NAME`, which `Request.Route` reads when every request class has a `Route`."""
    src = fx.src
    for n in walk(fx.tree.root_node):
        name = val = None
        if n.type == "enum_assignment":                                            # TS: enum RouteKey { Asset = 'assets' }
            _enum_member(n, src, ctx)
            continue
        if n.type in ("const_spec", "var_spec", "variable_declarator"):           # Go, TS/JS, C#
            name, val = n.child_by_field_name("name"), n.child_by_field_name("value")
            if val is None and n.type == "variable_declarator":                    # C#: identifier + equals_value_clause
                kids = [c for c in n.children if c.is_named]
                if len(kids) >= 2:
                    name, val = kids[0], kids[-1]
        elif n.type == "assignment" and n.parent is not None and (
                n.parent.type in ("module", "expression_statement")
                or n.parent.type == "block" and n.parent.parent is not None and n.parent.parent.type == "class_definition"):
            name, val = n.child_by_field_name("left"), n.child_by_field_name("right")    # Python (`X: str = ".."` in a class)
        if name is not None and val is not None and name.type in ("identifier", "property_identifier") and not in_function(n):
            while val.type in ("expression_list", "equals_value_clause") and val.named_child_count == 1:
                val = val.named_children[0]
            owner = owner_class(n, src)
            names = [text(name, src)] + ([f"{owner}.{text(name, src)}"] if owner else [])
            parts = _concat_parts(val, src) if val.type in CONCAT_NODES else \
                [("ref", text(val, src))] if n.type == "const_spec" and val.type == "identifier" else None   # Go `A = B`
            if parts:
                for nm in names:
                    ctx.define(nm, parts=parts)
            else:
                lit = first_string(val, src)
                if lit is not None and (PATH_LITERAL.match(lit) or REL_PATH_LITERAL.match(lit) or is_url_literal(lit)) and len(lit) > 1:
                    for nm in names:
                        ctx.define(nm, raw=lit)
                elif val.type in STRING_NODES and not has_interpolation(val) and lit is not None and _SEGMENT.match(lit):
                    for nm in names:
                        ctx.define(nm, segment=lit)
        if n.type in STRING_NODES:
            lit = unquote(text(n, src))
            if ENV_URL_NAME.match(lit):
                ctx.env_hints.add(lit)


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
    elif lit is not None and _SEGMENT.match(lit):
        ctx.define(name, segment=lit)


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
            parts.append(("ref", ".".join(text(c, src).split(".")[-2:])))
        else:
            parts.append(("unk", None))
    return parts if any(k == "lit" for k, _ in parts) else None


def valid_path(lit: str, lenient: bool = False) -> str | None:
    """The text of a string or template, as a path template — or None. A leading placeholder is a base URL
    (`{base}/v1/x` → `/v1/x`); `lenient` (a client's argument) also takes `items/{id}` and `{base}catalogBrands`."""
    lit = re.sub(r"\$\{[^}]*\}", "{param}", lit)
    m = re.match(r"^\{param\}(/?)(.*)$", lit)              # leading base-URL placeholder
    if m:
        rest = m.group(2)
        if m.group(1) == "/" or (lenient and (looks_like_rel_path(rest) or _ONE_WORD.match(rest))):
            lit = "/" + rest.lstrip("/")
        else:
            return None
    check = mask_placeholders(lit).split("?", 1)[0].split("#", 1)[0]    # `items/{id}?api-version=2.0`: the query is not the path
    if is_url_literal(lit) or PATH_LITERAL.match(check) or REL_PATH_LITERAL.match(lit):
        return lit if len(check) > 1 else None
    if lenient and looks_like_rel_path(check):
        return "/" + lit
    return None


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
        `lenient` (outbound-call arguments): accept `items/{id}` style relative paths too. Each expression is read once
        per file (memoized), so a long chain of reassignments — NSwag's `url_ = url_.replace(..)` and `url_ += "q=" ..`,
        two steps per parameter — costs one pass, and the depth guard only stops a pathological one."""
        memo = self._path_memo
        key = (n.id, lenient)
        if key not in memo:
            memo[key] = None if _depth > 64 else self._path_of(n, lenient, _depth)
        return memo[key]

    def _path_of(self, n: Node, lenient: bool, _depth: int) -> str | None:
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
        return valid_path(lit, lenient)

    def _path_of_name(self, n: Node, lenient: bool, _depth: int) -> str | None:
        """A local binding first (a parameter has no value here; a Go `url.URL` points where its `Path` was last set),
        then the directory's constants (`A.B` by its qualified name, else by `B`), then an imported one (`pkg.NAME`
        from the package's directory)."""
        name = text(n, self.src)
        if n.type == "identifier":
            moved = self._url_path(n, lenient, _depth)
            if moved is not None:
                return moved
            bound, val = self.scopes.binding(n)
            if bound:
                return self.path_of(val, lenient, _depth + 1) if val is not None else None
            owner = owner_class(n, self.src)                     # a class's own constant, used bare inside it
            if owner is not None and self.ctx.route_const(f"{owner}.{name}") is not None:
                return self.ctx.route_const(f"{owner}.{name}")
            if name in self.ctx.ambiguous:                        # other files of the directory define it too: this one's
                val = self.scopes.assigned_before(self.scopes.root, END, name)
                return self.path_of(val, lenient, _depth + 1) if val is not None else None
        elif n.type == "selector_expression" and name.endswith(".Path"):
            found = self._url_field(n, lenient, _depth)
            if found is not None:
                return found
        found = self.ctx.route_const(name)
        found = found if found is not None else self.foreign_const(name)
        if found is None and n.type == "identifier":            # a package var built by a call, used in a function
            val = self.scopes.assigned_before(self.scopes.root, END, name)     # (grpc-gateway's pattern_X = runtime.MustPattern(..))
            if val is not None and val.type in CALL_NODES:
                found = self.path_of(val, lenient, _depth + 1)
        return found

    def _url_path(self, obj: Node, lenient: bool, _depth: int) -> str | None:
        """Go's `url.URL` `u`, used here (`u.String()`, or `u` handed to a client): the path its last `u.Path = e` or
        `u.Path += e` before here sets; None when nothing sets it."""
        bound, val = self.scopes.binding(obj, text(obj, self.src) + ".Path")
        return self.path_of(val, lenient, _depth + 1) if bound and val is not None else None

    def _url_field(self, n: Node, lenient: bool, _depth: int) -> str | None:
        """`u.Path` read (`path.Join(u.Path, "/userinfo")`, `u.Path += "x"`): its last assignment before here, else the
        path of the URL `u` holds (`url.Parse("https://host/v1")`)."""
        bound, val = self.scopes.binding(n)
        if bound and val is not None:
            return self.path_of(val, lenient, _depth + 1)
        obj = n.child_by_field_name("operand")
        return self.path_of(obj, lenient, _depth + 1) if obj is not None and obj.type == "identifier" else None

    def foreign_const(self, name: str) -> str | None:
        """A constant of another directory the file imports (`BaseScanner`); None here."""
        return None

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
        pattern = re.match(r"^([A-Z]+) /", raw)                 # not "SELECT " + cols + " FROM x"
        if raw.startswith("/") or is_url_literal(raw) or REL_PATH_LITERAL.match(raw) or (pattern and pattern.group(1) in HTTP_METHODS):
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
        if fn is not None and fn.type == "selector_expression":                # Go's url.URL
            operand = fn.child_by_field_name("operand")
            if fname == "String" and not arg_nodes:                            # u.String(): where u points
                return self.path_of(operand, lenient, _depth + 1)
            if fname in ("Parse", "ParseRequestURI") and text(operand, self.src) == "url" and arg_nodes:
                return self.path_of(arg_nodes[0], lenient, _depth + 1)
            if fname == "JoinPath" and text(operand, self.src) != "url":       # u.JoinPath("x"): u's path, then "x"
                arg_nodes = [operand] + arg_nodes
            if text(operand, self.src) == "runtime" and fname == "MustPattern" and arg_nodes:
                return self.path_of(arg_nodes[0], lenient, _depth + 1)     # grpc-gateway
            if text(operand, self.src) == "runtime" and fname == "NewPattern" and len(arg_nodes) >= 3:
                ops = [int(text(c, self.src)) for c in walk(arg_nodes[1]) if c.type == "int_literal"]
                pool = [unquote(text(c, self.src)) for c in walk(arg_nodes[2]) if c.type == "interpreted_string_literal"]
                verb = unquote(text(arg_nodes[3], self.src)) if len(arg_nodes) > 3 and arg_nodes[3].type in STRING_NODES else ""
                return grpc_gateway_pattern(ops, pool, verb)
        if fname in ("Sprintf", "Errorf", "Format", "format"):
            if fname == "format" and fn is not None and fn.type == "attribute":      # "/v1/{}".format(x)
                recv = fn.child_by_field_name("object")
                rp = self.path_of(recv, lenient, _depth + 1) if recv is not None else None
                return rp.replace("{}", "{param}") if rp else None
            if fname == "Sprintf" and len(arg_nodes) > 1:
                filled = self._sprintf(arg_nodes[0], arg_nodes[1:], lenient, _depth)
                if filled:
                    return filled
            return self.path_of(arg_nodes[0], lenient, _depth + 1) if arg_nodes else None
        if fname in ("Replace", "ReplaceAll") and text(fn, self.src).startswith("strings.") and arg_nodes:
            return self.path_of(arg_nodes[0], lenient, _depth + 1)     # Go: strings.Replace(path, "{"+"id"+"}", v, -1)
        if fname in ("Replace", "replace", "TrimStart", "TrimEnd", "Trim", "ToLower", "ToLowerInvariant", "lstrip", "rstrip", "strip"):
            recv = fn.child_by_field_name("object") if fn is not None and fn.type == "attribute" else None
            if recv is None and fn is not None and fn.type in ("member_access_expression", "member_expression", "selector_expression"):
                kids_fn = [c for c in fn.children if c.is_named]
                recv = kids_fn[0] if kids_fn else None
            return self.path_of(recv, lenient, _depth + 1) if recv is not None else None
        if _JOIN_CALL.match(fname) and text(fn, self.src) != "strings.Join":        # strings.Join(cols, ", ") joins no path
            segs = [(unquote(text(a, self.src)) if a.type in STRING_NODES and not has_interpolation(a)
                     else self.path_of(a, lenient, _depth + 1)) or "{param}" for a in arg_nodes]
            segs = [s for s in segs if s]
            if fname == "urljoin" and len(segs) == 2 and segs[1].startswith("/"):
                return segs[1]                                   # urljoin(base, "/x"): the absolute path wins
            if len(segs) > 1 and segs[0] == "{param}":           # an unknown first part is the base URL, as in `base + "/x"`
                segs = segs[1:]
            if len(segs) > 1 and is_url_literal(segs[0]):         # a URL first keeps its host: the rest joins its path
                return segs[0].rstrip("/") + "/" + "/".join(s.strip("/") for s in segs[1:])
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
            if tail is not None and text(left, self.src).endswith(".Path") and not tail.startswith(("/", "http")):
                tail = "/" + tail                                # u.Path += "gettoken": the URL's own path ends in "/"
            ok = tail is not None and tail.startswith("/") and has_literal_segment(normalize_path(tail))
            return tail if ok else None
        return base + (tail if tail is not None else "{param}")

    def _interpolated(self, n: Node, lenient: bool = False, _depth: int = 0) -> str:
        """Template text with each substitution as `{param}`, except where the code holds the value (`_substitution`)."""
        tokens: list[str | Node | None] = []              # literal text, or the expression of a substitution
        for c in n.children:
            if c.type in INTERPOLATION_NODES:
                inner = [k for k in c.children if k.is_named and k.type != "interpolation_brace"]     # C# names its braces
                tokens.append(inner[0] if len(inner) == 1 else None)
            elif c.type in STRING_TEXT_NODES:
                tokens.append(text(c, self.src))
            # interpolation_start ($"), string_start/end, quotes: structural, no text
        raw = self._fill(tokens, lenient, _depth) if tokens else unquote(text(n, self.src))
        return re.sub(r"\{[^}]*\}", "{param}", raw) if n.type == "interpolated_string_expression" else raw

    def _fill(self, tokens: list[str | Node | None], lenient: bool, _depth: int, unknown: str = "{param}") -> str:
        """Literal text joined with the value of each substitution the code holds (`_substitution`), `unknown` for
        the others."""
        path_named = [t for t in tokens if isinstance(t, Node) and t.type == "identifier"
                      and _PATH_NAMED.match(text(t, self.src))]
        parts = []
        for i, t in enumerate(tokens):
            if isinstance(t, str) or t is None:
                parts.append(t if t is not None else unknown)
                continue
            prev, nxt = (tokens[i - 1] if i else ""), (tokens[i + 1] if i + 1 < len(tokens) else "")
            whole = (i == 0 or (isinstance(prev, str) and prev.endswith("/")),
                     i + 1 == len(tokens) or (isinstance(nxt, str) and nxt[:1] in ("/", "?", "#")))
            generic = any(o is not t for o in path_named)
            v = self._substitution(t, lenient, _depth, generic, whole)
            parts.append(v if v is not None else unknown)
        return "".join(parts)

    def _sprintf(self, fmt: Node, args: list[Node], lenient: bool, _depth: int) -> str | None:
        """`fmt.Sprintf("/%s/{id}", SchemasPath)`: a `%s`/`%v` whose argument the code holds as whole segments takes
        its value, as in a template; the other verbs stay, and an argument it does not hold stays a `%s`."""
        if fmt.type not in STRING_NODES or has_interpolation(fmt):
            return None
        lit, tokens, k, at = unquote(text(fmt, self.src)), [], 0, 0
        for m in re.finditer(r"%[-+# 0-9.]*[a-zA-Z%]", lit):
            tokens.append(lit[at:m.start()])
            verb = m.group(0)
            if verb == "%%":
                tokens.append("%")
            elif verb[-1] in "sv" and k < len(args):
                tokens.append(args[k])
                k += 1
            else:
                tokens.append(verb)
                k += 1
            at = m.end()
        tokens.append(lit[at:])
        tokens = [t for t in tokens if not (isinstance(t, str) and t == "")]
        if not any(isinstance(t, Node) for t in tokens):
            return None
        return valid_path(self._fill(tokens, lenient, _depth, unknown="%s"), lenient)

    def _substitution(self, e: Node, lenient: bool, _depth: int, generic: bool, whole: tuple[bool, bool]) -> str | None:
        """The value of `${e}` when the code holds it:
        - a local variable holding a path, read as in a concatenation (`url = `${url}?notify=true``);
        - a constant of the module or class holding a path, at the start of whole segments (`$"{baseUrl}items/{id}"`
          with `baseUrl = "api/catalog/"`, `$"{ApiUrlBase}/{orderId}"`) — but not in a generic wrapper, a template that
          takes the rest of the path from a variable named like one (`${prefix}/${API_PATH}${path}`, alertmanager;
          `${GHOST_URL}/ghost/api/admin/${endpoint}`): there the constant is only a base;
        - a word (a local or a constant: `resource = "cases"`) standing for one whole segment (`/${resource}/${id}`);
        - a call that is a path (`CombineUri(base, "api/orders")`), as whole segments; C# `nameof(X)`: the text `X`."""
        starts, ends = whole
        if e.type == "identifier":
            bound, val = self.scopes.binding(e)
            if bound:
                if val is None:
                    return None
                p = self.path_of(val, lenient, _depth + 1)
                return p if p is not None else (_word(val, self.src) if starts and ends else None)
            const = self._constant(e)
        elif e.type in NAME_NODES:                                 # `Routes.Orders`, `this.base`
            const = self._constant(e)
        elif e.type in CALL_NODES:
            m = re.match(r"^nameof\s*\(\s*([\w.]+)\s*\)$", text(e, self.src))
            if m:
                return m.group(1).split(".")[-1]
            p = self.path_of(e, lenient, _depth + 1)
            return p if p is not None and starts and ends else None
        else:
            return None
        if const is None:
            return None
        value, is_path = const
        if is_path:
            return value if not generic and starts and (ends or value.endswith("/")) else None
        return value if starts and ends else None

    def _constant(self, n: Node) -> tuple[str, bool] | None:
        """(value, holds a path) of the module or class constant an identifier names — this class's own first, then the
        directory's; a name the directory defines twice is this file's."""
        name = text(n, self.src)
        if name.split(".")[0] in ("this", "self"):                 # `this.base`: this class's own
            name = name.split(".")[-1]
        owner = owner_class(n, self.src)
        for key in ([f"{owner}.{name}"] if owner and "." not in name else []) + [name]:
            if (v := self.ctx.route_const(key)) is not None:
                return v, True
            if (w := self.ctx.segment_const(key)) is not None:
                return w, False
        if "." not in name and name in self.ctx.ambiguous:
            val = self.scopes.assigned_before(self.scopes.root, END, name)
            if val is not None:
                if (p := self.path_of(val)) is not None:
                    return p, True
                if (w := _word(val, self.src)) is not None:
                    return w, False
        return None

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
            if a.type == "identifier":                      # `let options_ = {method: "POST", ..}; fetch(url_, options_)`
                bound, val = self.scopes.binding(a)
                if bound and val is not None and val.type == "unary_expression" and val.named_child_count == 1:
                    val = val.named_children[0]                # res := &http.Request{Method: "GET", ..}; client.Do(res)
                if bound and val is not None and val.type not in OBJECT_NODES:
                    v = self._method_value(val)                # localVarHTTPMethod = http.MethodGet (openapi-generator)
                    if v:
                        return v
                a = val if bound and val is not None and val.type in OBJECT_NODES else a
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


def _word(n: Node, src: bytes) -> str | None:
    """A plain string literal holding one path segment (`"cases"`)."""
    if n.type not in STRING_NODES or has_interpolation(n):
        return None
    lit = unquote(text(n, src))
    return lit if _SEGMENT.match(lit) else None
