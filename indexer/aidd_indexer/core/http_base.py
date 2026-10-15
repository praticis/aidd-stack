"""Shared machinery for the per-language HTTP scanners (`languages/<lang>/http.py`).

`BaseScanner` knows how to turn an *expression* into a path template (`path_of`: literals, route
constants, local variables, concatenation, Sprintf/f-string/$""/${} templates, Join/Replace/Trim,
`new Uri`, `Format`), how to tell a handler argument from data (`is_handler_like`), how to read an
HTTP method out of arguments (`method_from_args`), and how to record endpoints and calls with
evidence. A language scanner only walks its tree and decides which calls are route registrations
and which are outbound requests — see `docs/indexer-evolution.md` for the rules table.

Route vs. client disambiguation (the main source of false positives): a call is a *route
registration* when the argument after the path is handler-like (a function literal, or a
selector/identifier that is not a string/nil/literal); it is an *outbound call* otherwise.
Test files and e2e/integration folders are skipped. Outbound paths made only of placeholders are dropped;
a route pattern goes through `route_path` (the root, constraints and converters, relative patterns on a group).
Every candidate carries evidence `repo:path:line`; the linker decides which endpoint a call
hits — here we only record what the code says.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from tree_sitter import Node

from ..languages.base import node_text as text, walk
from . import ids
from .config import TEST_FILE  # noqa: F401 — re-exported for the scanners / integrations
from .model import HttpCallInfo, HttpEndpointInfo, RepoInfo, SymbolInfo
from .scan_patterns import ScanPatterns  # noqa: F401 — re-exported for scanners / integrations
from .paths import (ENV_URL_NAME, path_key, HTTP_METHODS, PATH_LITERAL, REL_PATH_LITERAL, URL_LITERAL, VERB_BY_NAME,
                    has_literal_segment, looks_like_rel_path, mask_placeholders, normalize_path, unquote)


# --- outbound callee names -> method (None = look at the arguments) ---------------------------
OUTBOUND = {
    # Go helpers / net/http / resty
    "PostJSON": "POST", "GetJSON": "GET", "PutJSON": "PUT", "PatchJSON": "PATCH", "DeleteJSON": "DELETE",
    "DoJSON": None, "Do": None, "DoRequest": None, "Request": None, "Call": None, "Send": None, "Execute": None,
    "NewRequest": None, "NewRequestWithContext": None, "PostForm": "POST",
    # JS: axios / got / ky / superagent / fetch
    "fetch": None, "request": None, "$fetch": None, "ofetch": None,
    # C#: HttpClient
    "GetAsync": "GET", "GetStringAsync": "GET", "GetStreamAsync": "GET", "GetByteArrayAsync": "GET", "GetFromJsonAsync": "GET",
    "PostAsync": "POST", "PostAsJsonAsync": "POST", "PutAsync": "PUT", "PutAsJsonAsync": "PUT",
    "PatchAsync": "PATCH", "PatchAsJsonAsync": "PATCH", "DeleteAsync": "DELETE", "DeleteFromJsonAsync": "DELETE", "SendAsync": None,
    # Python: requests / httpx / aiohttp
    "get": "GET", "post": "POST", "put": "PUT", "patch": "PATCH", "delete": "DELETE", "head": "HEAD", "options": "OPTIONS",
    "Get": "GET", "Post": "POST", "Put": "PUT", "Patch": "PATCH", "Delete": "DELETE", "Head": "HEAD",
}
REQUEST_PATH_FIELDS = frozenset({"path", "url", "uri", "endpoint", "requesturi"})
GENERIC_OUTBOUND = {"Do", "DoRequest", "Request", "Call", "Send", "Execute", "request", "SendAsync", "DoJSON"}
CLIENT_RECEIVER = re.compile(r"(client|cli|http|https|resty|api|axios|fetch|got|ky|superagent|gateway|adapter|hc|requests|httpx|session|sess|aiohttp)$", re.I)

STRING_NODES = {"interpreted_string_literal", "raw_string_literal", "string", "string_literal", "template_string",
                "verbatim_string_literal", "interpolated_string_expression"}
# What delimits the scope of a local variable — an application object is recognised per (scope, name), so a
# `r` that is the application in `main` is not taken for the `r` a helper builds and returns.
FUNCTION_SCOPES = {"function_declaration", "method_declaration", "func_literal", "function_definition", "arrow_function",
                   "function_expression", "function", "method_definition", "generator_function_declaration",
                   "local_function_statement", "lambda_expression", "anonymous_method_expression", "lambda",
                   "constructor_declaration"}
HANDLER_NODES = {"func_literal", "arrow_function", "function_expression", "function", "lambda_expression",
                 "anonymous_method_expression", "lambda", "method_reference"}
NON_HANDLER_NODES = STRING_NODES | {"nil", "null", "none", "number", "int_literal", "integer", "float_literal", "true", "false",
                                    "composite_literal", "object", "array", "dictionary", "list", "object_creation_expression",
                                    "unary_expression", "boolean_literal", "null_literal", "character_literal"}


@dataclass
class HttpResult:
    endpoints: list[HttpEndpointInfo] = field(default_factory=list)
    calls: list[HttpCallInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ------------------------------------------------------------------------------------------
class PackageContext:
    """Per directory (Go package / TS folder / C# namespace dir): route constants and env-var names."""

    def __init__(self, patterns: "ScanPatterns | None" = None) -> None:
        self.route_consts: dict[str, str] = {}     # name -> raw path (or base URL)
        self.const_parts: dict[str, list[tuple[str, str | None]]] = {}   # name -> `A + "/x"` as ("ref", "A"), ("lit", "/x")
        self.env_hints: set[str] = set()
        self.patterns = patterns or ScanPatterns()
        self.functions_by_name: dict[str, list[SymbolInfo]] = {}   # functions/methods of every file in the dir

    def route_const(self, name: str, _seen: tuple[str, ...] = ()) -> str | None:
        """Raw path of a module-level constant; one built from others (`RouteItem = RouteCollection + "/{id}"`)
        is resolved on first use, since the constants it names may live in another file of the directory."""
        if name in self.route_consts:
            return self.route_consts[name]
        parts = self.const_parts.get(name)
        if parts is None or name in _seen or len(_seen) > 4:
            return None
        raw = ""
        for kind, v in parts:
            r = v if kind == "lit" else (self.route_const(v, _seen + (name,)) if kind == "ref" and v else None)
            raw += r if r is not None else "{param}"
        raw = re.sub(r"^\{param\}(?=/)", "", raw)
        if len(raw) < 2 or not (PATH_LITERAL.match(mask_placeholders(raw)) or REL_PATH_LITERAL.match(raw) or URL_LITERAL.match(raw)):
            return None
        self.route_consts[name] = raw
        return raw


def dir_of(file_path: str) -> str:
    return str(PurePosixPath(file_path).parent)


_HINT_DIRS = ("outbound", "clients", "client", "gateways", "gateway", "integrations", "integration", "external",
              "providers", "provider", "adapters", "services", "service", "apis", "sdk", "connectors")


def target_hint(file_path: str) -> str:
    """'internal/adapters/outbound/billing/client.go' -> 'billing'; falls back to the dir name."""
    parts = PurePosixPath(file_path).parent.parts
    for i, part in enumerate(parts):
        if part.lower() in _HINT_DIRS and i + 1 < len(parts):
            nxt = parts[i + 1]
            if nxt.lower() not in ("http", "rest", "grpc", "outbound", "inbound", "v1", "v2"):
                return nxt
            if i + 2 < len(parts):
                return parts[i + 2]
    stem = PurePosixPath(file_path).stem
    m = re.match(r"^(.*?)[._-]?(client|service|api|gateway|adapter|http)$", stem, re.I)   # BillingClient.cs, users.service.ts
    if m and m.group(1):
        return m.group(1)
    return parts[-1] if parts else ""

CONCAT_NODES = {"binary_expression", "binary_operator"}


def collect_constants(fx, ctx: PackageContext) -> None:
    """Module- and class-level constants holding a path or a base URL. A function's locals are not constants of the
    directory: a `url` parameter elsewhere would take the value of this function's `url` (resolve_local reads them)."""
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


def in_function(n: Node) -> bool:
    p = n.parent
    while p is not None:
        if p.type in FUNCTION_SCOPES:
            return True
        p = p.parent
    return False


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
        elif c.type in STRING_NODES and not any(k.type in ("interpolation", "template_substitution") for k in c.children):
            parts.append(("lit", unquote(text(c, src))))
        elif c.type in ("identifier", "selector_expression", "member_expression", "member_access_expression", "attribute"):
            parts.append(("ref", text(c, src).split(".")[-1]))
        else:
            parts.append(("unk", None))
    return parts if any(k == "lit" for k, _ in parts) else None


def first_string(n: Node, src: bytes) -> str | None:
    if n.type in STRING_NODES:
        return unquote(text(n, src))
    for c in n.children:
        if c.type in ("call_expression", "invocation_expression", "call"):
            continue                       # don't mine literals out of calls (env("X"), t("key"))
        r = first_string(c, src)
        if r is not None:
            return r
    return None


# ------------------------------------------------------------------------------------------
class BaseScanner:
    framework_default = "unknown"
    relative_on_groups = False      # the framework joins a group prefix and a pattern without a leading slash (gin, MapGroup)

    def __init__(self, repo: RepoInfo, fx, ctx: PackageContext, out: HttpResult):
        self.repo, self.fx, self.ctx, self.out = repo, fx, ctx, out
        self.src = fx.src
        self.symbols_by_name: dict[str, list[SymbolInfo]] = {}
        for s in fx.symbols:
            self.symbols_by_name.setdefault(s.name, []).append(s)
        self.group_prefix: dict[str, str] = {}   # router/group variable -> path prefix
        self.router_vars: set[str] = set()       # identifiers known to be routers/groups/apps
        self.app_vars: set[tuple[int, str]] = set()   # (scope, name) of the application itself, not a sub-router

    def scope_of(self, n: Node) -> int:
        p = n.parent
        while p is not None and p.type not in FUNCTION_SCOPES:
            p = p.parent
        return p.id if p is not None else 0

    def mark_app(self, name: str, at: Node) -> None:
        """`name`, assigned at `at`, is the application (`gin.Default()`, `express()`, `FastAPI()`, `builder.Build()`)."""
        self.app_vars.add((self.scope_of(at), name))

    def is_app(self, name: str, at: Node) -> bool:
        return (self.scope_of(at), name) in self.app_vars

    def route_path(self, n: Node, receiver: str, at: Node) -> str | None:
        """Pattern of a route registration on `receiver` (the call is `at`): what `path_of` accepts, plus what
        only a route pattern can be —
        - the root (`"/"`, `""`) when its full path is known: the receiver is the application itself or a group
          with a prefix of its own. A sub-router's root is wherever it gets mounted, so it is not a route here;
        - placeholders with constraints, converters or optional markers (`{id:int?}`, `{name:minlength(1)}`,
          `{slug:[a-z-]+}`, `<int:id>`, `<any(a, b):page>`, `:id?`);
        - on a group, a pattern without the leading slash (`v1.GET("users")`, `api.MapGet("{orderId:int}")`) — only where
          the framework joins them (`relative_on_groups`): Flask, Starlette and Express require the slash."""
        p = self.path_of(n)
        if p is not None:
            return "/" + p if self.relative_on_groups and not p.startswith(("/", "http")) and receiver in self.group_prefix else p
        if n.type not in STRING_NODES or n.type == "interpolated_string_expression" \
                or any(c.type in ("interpolation", "template_substitution") for c in n.children):
            return None
        lit = unquote(text(n, self.src)).strip()
        if lit in ("", "/"):
            return "/" if self.group_prefix.get(receiver) or self.is_app(receiver, at) else None
        masked = mask_placeholders(lit)
        if PATH_LITERAL.match(masked):
            return lit
        if self.relative_on_groups and receiver in self.group_prefix and PATH_LITERAL.match("/" + masked):
            return "/" + lit
        return None

    def evidence(self, node: Node) -> str:
        return f"{self.repo.name}:{self.fx.file.path}:{node.start_point[0] + 1}"

    def is_client_receiver(self, recv_last: str) -> bool:
        return bool(CLIENT_RECEIVER.search(recv_last)) or self.ctx.patterns.is_client(recv_last)

    def convention_call(self, n: Node, name: str, recv_last: str, callee: str, arg_nodes: list[Node]) -> bool:
        """Route registrars / client methods declared by a convention (`ScanPatterns`). Called first by
        every language scanner; True = recorded (or deliberately ignored), stop here."""
        pats = self.ctx.patterns
        if name in pats.registrars and len(arg_nodes) >= 2:
            fixed = pats.registrars[name]
            path_idx = next((i for i, a in enumerate(arg_nodes) if self.path_of(a) is not None), None)
            if path_idx is not None:
                method = fixed or self.method_from_args(arg_nodes[:path_idx + 1]) or "ANY"
                handler = next((a for a in reversed(arg_nodes) if self.is_handler_like(a)), None)
                self.add_endpoint(n, method, self.path_of(arg_nodes[path_idx]) or "", "convention", handler,
                                  prefix=self.group_prefix.get(recv_last, ""))
                return True
        if name in pats.clients or (name in GENERIC_OUTBOUND and pats.is_client(recv_last)):
            method = pats.clients.get(name) or OUTBOUND.get(name) or self.method_from_args(arg_nodes)
            for a in arg_nodes:
                p = self.path_of(a, lenient=True)
                if p is not None:
                    self.add_call(n, method, p, callee)
                    return True
        return False

    # -- template of an interpolated string (Python f"", C# $"", JS `${}`) ------------------
    def _interpolated(self, n: Node, lenient: bool = False, _depth: int = 0) -> str:
        """Template text with each substitution as `{param}` — except a local variable holding a path, read as in a
        concatenation (`url = `${url}?notify=true``). A module constant stays a placeholder: in a generic wrapper
        (`${prefix}/${API_PATH}${path}`) it would make a path out of what is only a base."""
        parts = []
        for c in n.children:
            if c.type in ("interpolation", "template_substitution"):
                inner = [k for k in c.children if k.is_named]
                v = None
                if len(inner) == 1 and inner[0].type == "identifier":
                    bound, val = self.local_binding(inner[0])
                    v = self.path_of(val, lenient, _depth + 1) if bound and val is not None else None
                parts.append(v if v is not None else "{param}")
            elif c.type in ("string_content", "string_fragment", "interpolated_string_text", "escape_sequence"):
                parts.append(text(c, self.src))
            # interpolation_start ($"), string_start/end, quotes: structural, no text
        raw = "".join(parts) if parts else unquote(text(n, self.src))
        return re.sub(r"\{[^}]*\}", "{param}", raw) if n.type == "interpolated_string_expression" else raw

    # -- local variables: `uri := base + "/v1/x"` two lines above the call ----------------------
    _FUNC_NODES = FUNCTION_SCOPES

    def resolve_local(self, ident: Node) -> Node | None:
        """Value expression of the closest preceding assignment to this identifier in its scope (see `local_binding`)."""
        return self.local_binding(ident)[1]

    def local_binding(self, ident: Node) -> tuple[bool, Node | None]:
        """Where a name is bound, from the enclosing function outward: (True, value) for an assignment that
        precedes it, (True, None) for a parameter — the caller's value, unknown here — and (False, None) when no
        enclosing function binds it (a module-level constant, then). Code at module level reads the module."""
        name = text(ident, self.src)
        scope = ident.parent
        while True:
            while scope is not None and scope.type not in self._FUNC_NODES:
                scope = scope.parent
            if scope is None:
                if in_function(ident):
                    return False, None
                val = self._assigned_before(self.fx.tree.root_node, ident, name)
                return val is not None, val
            val = self._assigned_before(scope, ident, name)
            if val is not None:
                return True, val
            if self._is_parameter(scope, name):
                return True, None
            scope = scope.parent

    def _is_parameter(self, scope: Node, name: str) -> bool:
        for field_name in ("parameters", "parameter", "receiver"):
            params = scope.child_by_field_name(field_name)
            if params is not None and any(d.type == "identifier" and text(d, self.src) == name for d in walk(params)):
                return True
        return False

    def _assigned_before(self, scope: Node, ident: Node, name: str) -> Node | None:
        """Value of the last assignment to `name` before `ident` in `scope`, leaving out the bodies of other functions."""
        best: Node | None = None
        stack = [scope]
        while stack:
            d = stack.pop()
            if d.start_byte >= ident.start_byte:
                continue
            inside = d.start_byte <= ident.start_byte < d.end_byte
            if d is not scope and d.type in self._FUNC_NODES and not inside:
                continue
            stack.extend(reversed(d.children))
            if inside:
                continue                     # `url = `${url}?x`` — the name on the right is the earlier value
            if self._appends_to(d, name):
                best = d                     # `url += "/" + id`: read by path_of as the earlier value plus this
                continue
            if d.type in ("short_var_declaration", "assignment_statement", "assignment", "assignment_expression", "variable_declarator", "var_spec"):
                left = d.child_by_field_name("left") or d.child_by_field_name("name")
                right = d.child_by_field_name("right") or d.child_by_field_name("value")
                if d.type == "variable_declarator" and right is None:                 # C#
                    kids = [c for c in d.children if c.is_named]
                    if len(kids) >= 2:
                        left, right = kids[0], kids[-1]
                        if right.type == "equals_value_clause":
                            inner = [c for c in right.children if c.is_named]
                            right = inner[-1] if inner else right
                if left is None or right is None:
                    continue
                lefts = [c for c in left.children if c.is_named] if left.type == "expression_list" else [left]
                rights = [c for c in right.children if c.is_named] if right.type == "expression_list" else [right]
                for i, l in enumerate(lefts):
                    if text(l, self.src) == name and i < len(rights) and (best is None or d.start_byte > best.start_byte):
                        best = rights[i]
        return best

    def _appends_to(self, d: Node, name: str) -> bool:
        """`name += expr` (JS/Python/C# augmented assignment, Go `+=` assignment statement)."""
        if d.type not in ("augmented_assignment_expression", "augmented_assignment", "assignment_statement", "assignment_expression"):
            return False
        op, left = d.child_by_field_name("operator"), d.child_by_field_name("left")
        return op is not None and left is not None and text(op, self.src) == "+=" and text(left, self.src) == name

    # -- assembling a path from an expression ---------------------------------------------
    def path_of(self, n: Node, lenient: bool = False, _depth: int = 0) -> str | None:
        """Best-effort path template for an argument expression, or None when it is not path-like.
        `lenient` (outbound-call arguments): accept `items/{id}` style relative paths too."""
        t = n.type
        src = self.src
        if _depth > 4:
            return None
        if t in STRING_NODES:
            has_interp = any(c.type in ("interpolation", "template_substitution") for c in n.children)
            lit = self._interpolated(n, lenient, _depth) if has_interp or t == "interpolated_string_expression" else unquote(text(n, src))
            lit = re.sub(r"\$\{[^}]*\}", "{param}", lit)
            m = re.match(r"^\{param\}(/?)(.*)$", lit)              # leading base-URL placeholder
            if m:
                rest = m.group(2)
                if m.group(1) == "/" or (lenient and (looks_like_rel_path(rest) or re.match(r"^[A-Za-z][A-Za-z0-9_\-]{2,}(\?.*)?$", rest))):
                    lit = "/" + rest.lstrip("/")
                else:
                    return None
            check = mask_placeholders(lit).split("?", 1)[0].split("#", 1)[0]    # `items/{id}?api-version=2.0`: the query is not the path
            if URL_LITERAL.match(lit) or PATH_LITERAL.match(check) or REL_PATH_LITERAL.match(lit):
                return lit if len(check) > 1 else None
            if lenient and looks_like_rel_path(check):
                return "/" + lit
            return None
        if t in ("identifier", "selector_expression", "member_expression", "property_identifier", "member_access_expression", "attribute"):
            if t == "identifier":
                bound, val = self.local_binding(n)
                if bound:
                    return self.path_of(val, lenient, _depth + 1) if val is not None else None
            return self.ctx.route_const(text(n, src).split(".")[-1])
        if t in ("binary_expression", "concatenated_string", "binary_operator"):   # base + "/v1/x" + id
            raw = ""
            lead = False                                 # an unknown first operand: a base URL
            operands: list[Node] = []                    # flatten `a + b + c + ...` (left-nested) into one list
            stack = [c for c in reversed(n.children) if c.is_named]
            while stack:
                c = stack.pop()
                if c.type == t:
                    stack.extend(k for k in reversed(c.children) if k.is_named)
                else:
                    operands.append(c)
            for c in operands:
                verb = re.match(r"^(?:http\.)?Method([A-Z][a-z]+)$", text(c, src))        # http.MethodPut + " " + path
                if verb and verb.group(1).upper() in HTTP_METHODS:
                    raw += verb.group(1).upper()
                    continue
                p = self.path_of(c, lenient, _depth + 1) if c.type not in STRING_NODES else (self._interpolated(c, lenient, _depth + 1) if any(k.type in ("interpolation", "template_substitution") for k in c.children) else unquote(text(c, src)))
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
            if lenient and lead and re.match(r"^[A-Za-z][A-Za-z0-9_\-]{2,}(\?.*)?$", raw):
                return "/" + raw                                     # base + 'message' (gotify)
            return ("/" + raw) if lenient and "/" in raw and not raw.startswith("{") else None
        if t in ("call_expression", "invocation_expression", "call"):     # fmt.Sprintf("/v1/%s", id), "...".format(), path.Join
            fn = n.child_by_field_name("function")
            args = n.child_by_field_name("arguments")
            if fn is None:      # C#: invocation_expression children = [member_access|identifier, argument_list]
                kids = [c for c in n.children if c.is_named]
                fn, args = (kids[0] if kids else None), next((c for c in kids if c.type == "argument_list"), None)
            fname = text(fn, src).split(".")[-1] if fn is not None else ""
            if args is None:
                return None
            arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named]
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
                segs = [(unquote(text(a, src)) if a.type in STRING_NODES and not any(k.type in ("interpolation", "template_substitution") for k in a.children)
                         else self.path_of(a, lenient, _depth + 1)) or "{param}" for a in arg_nodes]
                segs = [s for s in segs if s]
                return ("/" + "/".join(s.strip("/") for s in segs)) if segs else None
            return None
        if t in ("composite_literal", "object", "dictionary", "anonymous_object_creation_expression"):   # Request{Path: p} / {url: p}
            for key, val in self._keyed_fields(n):
                if key.lower() in REQUEST_PATH_FIELDS:
                    return self.path_of(val, True, _depth + 1)
            return None
        if t == "object_creation_expression":             # new Uri("api/x", UriKind.Relative)
            if "Uri" in text(n, src).split("(")[0]:
                args = next((c for c in n.children if c.type == "argument_list"), None)
                arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named] if args else []
                return self.path_of(arg_nodes[0], lenient, _depth + 1) if arg_nodes else None
            return None
        if t in ("augmented_assignment_expression", "augmented_assignment", "assignment_statement", "assignment_expression"):
            left, right = n.child_by_field_name("left"), n.child_by_field_name("right")      # `url += "/" + id`
            if left is None or right is None or not self._appends_to(n, text(left, src)):
                return None
            left, right = (x.named_children[0] if x.type == "expression_list" and x.named_child_count == 1 else x for x in (left, right))
            base = self.path_of(left, lenient, _depth + 1)
            tail = self.path_of(right, lenient, _depth + 1) if right.type not in STRING_NODES else unquote(text(right, src))
            if base is None:                                # base URL from a call: the appended path is what we know —
                ok = tail is not None and tail.startswith("/") and has_literal_segment(normalize_path(tail))
                return tail if ok else None                 # not a bare "/" onto a parameter (chi FileServer)
            return base + (tail if tail is not None else "{param}")
        if t in ("parenthesized_expression", "await_expression", "unary_expression"):
            inner = [c for c in n.children if c.is_named]
            return self.path_of(inner[0], lenient, _depth + 1) if inner else None
        if t in ("argument", "keyword_argument"):
            inner = [c for c in n.children if c.is_named]
            return self.path_of(inner[-1], lenient, _depth + 1) if inner else None
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

    def _unwrap_arg(self, n: Node) -> Node:
        if n.type in ("argument", "variadic_argument", "spread_element"):   # C# argument, Go `h...`, JS `...h`
            inner = [c for c in n.children if c.is_named]
            return inner[-1] if inner else n
        return n

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
            if a.type in ("object", "composite_literal", "dictionary", "anonymous_object_creation_expression"):
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
        m = re.match(r"^(?:http\.)?Method([A-Z][a-z]+)$|^HttpMethod\.([A-Z][a-z]+)$", txt)
        if m:
            v = (m.group(1) or m.group(2) or "").upper()
            return v if v in HTTP_METHODS else None
        if n.type in ("identifier", "shorthand_property_identifier"):
            return self._method_value(self.resolve_local(n), depth + 1)
        return None

    def is_handler_like(self, n: Node | None) -> bool:
        """The argument after a route path: a function value, not data."""
        if n is None:
            return False
        n = self._unwrap_arg(n)
        if n.type in HANDLER_NODES:
            return True
        if n.type in NON_HANDLER_NODES:
            return False
        txt = text(n, self.src)
        if n.type in ("identifier", "selector_expression", "member_expression", "member_access_expression", "attribute"):
            return not txt.lower() in ("nil", "null", "none", "undefined") and not re.search(r"\b(ctx|context|req|request|body|payload|opts|options|params|headers)\b$", txt, re.I)
        if n.type in ("call_expression", "invocation_expression", "call"):
            # http.HandlerFunc(x), middleware(h), wrap(h), timeout(5, h) → handler-ish; fmt.Sprintf/data builders → not
            return not re.search(r"\b(Sprintf|Errorf|Marshal|Join|format|Encode|Serialize|bytes\.|strings\.)", txt)
        return False

    def _function_symbol(self, name: str):
        """The function a handler name refers to: this file first, else the only one with that name
        in the directory (a Go package / a controller folder spans files); two homonyms → None."""
        cands = [c for c in self.symbols_by_name.get(name) or [] if c.kind in ("function", "method")]
        if cands:
            return cands[0]
        pkg = self.ctx.functions_by_name.get(name) or []
        return pkg[0] if len(pkg) == 1 else None

    def _handler_in_call(self, call: Node, depth: int = 0):
        """`mw(h, WithX())`, `http.HandlerFunc(h)`, `chain(a, b)(h)`: the first argument (depth-first,
        the callee of a curried call included) that names a function of this repo. Option calls
        with no function argument (`WithX()`) are skipped."""
        if depth > 3:
            return None
        fn = call.child_by_field_name("function")
        args = call.child_by_field_name("arguments")
        kids = [c for c in args.children if c.is_named] if args is not None else []
        if fn is None:                       # C#
            named = [c for c in call.children if c.is_named]
            fn = named[0] if named else None
            al = next((c for c in named if c.type == "argument_list"), None)
            kids = [self._unwrap_arg(c) for c in al.children if c.is_named] if al is not None else []
        for a in kids:
            a = self._unwrap_arg(a)
            if a.type in HANDLER_NODES:
                return "<inline>", None
            if a.type in ("identifier", "selector_expression", "member_expression", "member_access_expression", "attribute"):
                sym = self._function_symbol(text(a, self.src).split(".")[-1])
                if sym is not None:
                    return sym.name, sym.id
            elif a.type in ("call_expression", "invocation_expression", "call"):
                found = self._handler_in_call(a, depth + 1)
                if found:
                    return found
        if fn is not None and fn.type in ("call_expression", "invocation_expression", "call"):
            return self._handler_in_call(fn, depth + 1)
        return None

    def resolve_handler(self, handler_node: Node | None) -> tuple[str | None, str | None]:
        if handler_node is None:
            return None, None
        node = self._unwrap_arg(handler_node)
        if node.type in HANDLER_NODES:
            return "<inline>", None
        if node.type in ("call_expression", "invocation_expression", "call"):
            found = self._handler_in_call(node)
            if found:
                return found
        txt = text(node, self.src).strip()
        m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*\)*\s*$", txt)
        name = m.group(1) if m else None
        if not name or name.lower() in ("nil", "null", "none"):
            return None, None
        sym = self._function_symbol(name)
        return name, (sym.id if sym else None)

    def add_endpoint(self, node: Node, method: str, raw_pattern: str, framework: str, handler_node: Node | None,
                     prefix: str = "", handler_name: str | None = None, handler_id: str | None = None) -> None:
        pat = (raw_pattern or "").strip()
        m = re.match(r"^([A-Z]+)\s+(/.*)$", pat)
        if m and m.group(1) in HTTP_METHODS:
            method, pat = m.group(1), m.group(2)
        full = (prefix.rstrip("/") + "/" + pat.lstrip("/")) if prefix else pat
        path = normalize_path(full)
        if handler_name is None and handler_node is not None:
            handler_name, handler_id = self.resolve_handler(handler_node)
        self.out.endpoints.append(HttpEndpointInfo(
            id=ids.http_endpoint(self.repo.tenant, self.repo.name, method or "ANY", path_key(path)),
            method=method or "ANY", path=path, raw_pattern=raw_pattern, framework=framework,
            file_id=self.fx.file.id, line=node.start_point[0] + 1,
            handler_name=handler_name, handler_id=handler_id, evidence=self.evidence(node),
        ))

    def add_call(self, node: Node, method: str | None, raw_path: str, via: str) -> None:
        path = normalize_path(raw_path)
        if not has_literal_segment(path):
            return
        caller = self.fx._enclosing_symbol(node)
        self.out.calls.append(HttpCallInfo(
            id=ids.http_call(self.repo.tenant, self.repo.name, self.repo.ref, self.fx.file.path, node.start_point[0] + 1),
            method=(method or "ANY").upper(), path=path, raw_path=raw_path, via=via[-60:],
            target_hint=target_hint(self.fx.file.path), env_hints=sorted(self.ctx.env_hints),
            file_id=self.fx.file.id, line=node.start_point[0] + 1,
            caller_id=caller.id if caller else self.fx.file.id, evidence=self.evidence(node),
        ))

    # -- shared: `x := r.Group("/v1")` style prefix tracking -------------------------------
    def _record_group(self, names: list[str], call: Node, fn_text: str, arg_nodes: list[Node]) -> None:
        recv = fn_text.rsplit(".", 1)[0] if "." in fn_text else ""
        base = self.group_prefix.get(recv.split(".")[-1], "")
        p = self.path_of(arg_nodes[0]) if arg_nodes else None
        p = p if p is not None else ""
        for nm in names:
            self.group_prefix[nm] = (base.rstrip("/") + p) if p else base
            self.router_vars.add(nm)

