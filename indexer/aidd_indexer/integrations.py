"""Integration candidates v0 (ROADMAP F0.4): HTTP routes a repo EXPOSES and outbound HTTP
calls it makes with a literal (or template) path.

Deterministic, tree-sitter based, no LLM. Calibrated on a public corpus (chi, gin, fiber
recipes, gorilla, alertmanager, express, nest, fastify, eShop, CleanArchitecture, fastapi,
flask) besides the tenant's own repos — see docs/ROADMAP.md F0.4.

Exposed routes
  Go      mux.HandleFunc("POST /v1/x", h)   net/http >= 1.22 (method in the pattern)
          mux.HandleFunc("/v1/x", h)        method ANY · gorilla: `.Methods("GET")` chained
          r.Get("/x", h) / r.GET / app.Get  chi · gin/echo · fiber (+ Group("/prefix") vars)
  TS/JS   router.get("/x", handler)         express / koa / fastify (2nd arg is a function)
          @Controller("p") + @Get(":id")    NestJS
  C#      [Route("api/[controller]")] + [HttpGet("{id}")]        MVC / API controllers
          app.MapGet("/x", ...) / group = app.MapGroup("/p")    minimal APIs
  Python  @app.get("/x") / @router.post   FastAPI (+ APIRouter(prefix=...))
          @app.route("/x", methods=[..])   Flask / Blueprint

Outbound calls
  route constants (`const routeX = "/v1/x"`), Sprintf / f-strings / $"..." / `${}` templates,
  string concatenation, `http.NewRequest(method, url)`, PostJSON-like helpers, resty,
  axios/fetch/got, HttpClient.*Async, `new HttpRequestMessage(HttpMethod.X, "/p")`,
  requests/httpx/aiohttp.  Normalized to a path template with {param} placeholders.

Route vs. client disambiguation (the main source of false positives): a call is a *route
registration* when the argument after the path is handler-like (a function literal, or a
selector/identifier that is not a string/nil/literal); it is an *outbound call* otherwise.
Test files and e2e/integration folders are skipped. Paths made only of placeholders are
dropped. Every candidate carries evidence `repo:path:line`; the linker (F0.5) decides which
endpoint a call hits — here we only record what the code says.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from tree_sitter import Node

from . import ids
from .model import HttpCallInfo, HttpEndpointInfo, RepoInfo, SymbolInfo

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
VERB_BY_NAME = {v.lower(): v for v in HTTP_METHODS} | {v.capitalize(): v for v in HTTP_METHODS} | {v: v for v in HTTP_METHODS}

# --- route registration callee names ----------------------------------------------------------
GO_REGISTRARS = {"HandleFunc", "Handle", "Any", "Match", "All"} | set(VERB_BY_NAME)      # net/http, gorilla, chi, gin, echo, fiber
GO_MOUNTS = {"Group", "PathPrefix", "Route", "Mount", "Subrouter"}                       # prefix carriers
TS_REGISTRARS = {"get", "post", "put", "patch", "delete", "head", "options", "all", "route"}
CS_MAP = {"MapGet": "GET", "MapPost": "POST", "MapPut": "PUT", "MapPatch": "PATCH", "MapDelete": "DELETE", "MapMethods": None, "Map": "ANY"}
CS_HTTP_ATTR = {"HttpGet": "GET", "HttpPost": "POST", "HttpPut": "PUT", "HttpPatch": "PATCH", "HttpDelete": "DELETE", "HttpHead": "HEAD", "HttpOptions": "OPTIONS"}
PY_REGISTRARS = {"get", "post", "put", "patch", "delete", "head", "options", "route", "api_route", "websocket"}

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
GENERIC_OUTBOUND = {"Do", "DoRequest", "Request", "Call", "Send", "Execute", "request", "SendAsync", "DoJSON"}
CLIENT_RECEIVER = re.compile(r"(client|cli|http|https|resty|api|axios|fetch|got|ky|superagent|gateway|adapter|hc|requests|httpx|session|sess|aiohttp)$", re.I)

PATH_LITERAL = re.compile(r"^/[A-Za-z0-9_\-./{}:%$*\[\]]*$")
REL_PATH_LITERAL = re.compile(r"^(api|v\d+)/[A-Za-z0-9_\-./{}:%$*\[\]?=&]*$")        # C#/JS clients often omit the leading slash
URL_LITERAL = re.compile(r"^https?://[^/\s]+(/.*)?$")
ENV_URL_NAME = re.compile(r"^[A-Z][A-Z0-9_]*(URL|HOST|ENDPOINT|BASE_URL|ADDR|BASEURL)$")
TEST_FILE = re.compile(r"(_test\.go$|\.spec\.[tj]sx?$|\.test\.[tj]sx?$|(^|/)test_[^/]*\.py$|_test\.py$|conftest\.py$|"
                       r"Tests?\.cs$|/tests?/|/testdata/|/mocks?/|/e2e/|/integration[-_]tests?/|/__tests__/|\.Tests?/|/testing/)")
STRING_NODES = {"interpreted_string_literal", "raw_string_literal", "string", "string_literal", "template_string",
                "verbatim_string_literal", "interpolated_string_expression"}
HANDLER_NODES = {"func_literal", "arrow_function", "function_expression", "function", "lambda_expression",
                 "anonymous_method_expression", "lambda", "method_reference"}
NON_HANDLER_NODES = STRING_NODES | {"nil", "null", "none", "number", "int_literal", "integer", "float_literal", "true", "false",
                                    "composite_literal", "object", "array", "dictionary", "list", "object_creation_expression",
                                    "unary_expression", "boolean_literal", "null_literal", "character_literal"}


def _text(n: Node, src: bytes) -> str:
    return src[n.start_byte:n.end_byte].decode("utf-8", errors="replace")


def _unquote(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^[fFrRbBuU$@]{1,3}(?=[\"'`])", "", s)     # f"..", $"..", @"..", rb".."
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'`":
        return s[1:-1]
    return s


def path_key(path: str) -> str:
    """Comparison key: every placeholder becomes {param} — `/v1/users/{id}` == `/v1/users/{param}`."""
    return re.sub(r"\{[^}]*\}", "{param}", path)


def normalize_path(path: str) -> str:
    """Route/template → canonical `/a/{param}/b`. Idempotent."""
    p = path.strip()
    m = URL_LITERAL.match(p)
    if m:
        p = m.group(1) or "/"
    p = p.split("?", 1)[0].split("#", 1)[0]
    p = re.sub(r"%[sdvq]", "{param}", p)                          # Sprintf verbs
    p = re.sub(r"\$\{[^}]*\}", "{param}", p)                      # JS template literals
    p = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\s*:[^}]*\}", r"{\1}", p)   # {id:int} (ASP.NET) → {id}
    p = re.sub(r"\{\*+([A-Za-z_][A-Za-z0-9_]*)\}", r"{\1}", p)   # {*rest} (ASP.NET catch-all)
    p = re.sub(r"<(?:[a-z_]+:)?([A-Za-z_][A-Za-z0-9_]*)>", r"{\1}", p)  # <int:id> (Flask)
    p = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)\??", r"{\1}", p)      # :id (gin, express, echo)
    p = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)(\.\.\.)?\}", r"{\1}", p)  # {id...} → {id}
    p = re.sub(r"\[controller\]", "{controller}", p, flags=re.I)  # ASP.NET token (resolved later by the linker)
    p = re.sub(r"\[action\]", "{action}", p, flags=re.I)
    p = re.sub(r"\*\w*", "{rest}", p)                             # wildcards
    p = re.sub(r"^\{[^}]*\}(?=/)", "", p)                         # leading base-URL placeholder: {base}/v1 → /v1
    p = re.sub(r"/{2,}", "/", p)
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    if not p.startswith("/"):
        p = "/" + p
    return p


_NOT_A_PATH_HEAD = {"application", "text", "image", "multipart", "audio", "video", "message", "font", "model",
                    "http", "https", "utf", "bearer", "basic", "true", "false"}


def _looks_like_rel_path(s: str) -> bool:
    """`items/{id}`, `catalog/brands?x=1` — but not `application/json` or `a/b.txt`."""
    if not re.match(r"^[A-Za-z][A-Za-z0-9_\-]*/[A-Za-z0-9_\-./{}?=&:%]*$", s):
        return False
    head = s.split("/", 1)[0].lower()
    return head not in _NOT_A_PATH_HEAD and not re.search(r"\.(json|xml|txt|html|js|css|png|jpg|svg|ya?ml|csv|pdf)$", s, re.I)


def _has_literal_segment(path: str) -> bool:
    return any(seg and not seg.startswith("{") for seg in path.split("/"))


@dataclass
class HttpResult:
    endpoints: list[HttpEndpointInfo] = field(default_factory=list)
    calls: list[HttpCallInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ------------------------------------------------------------------------------------------
class _PackageContext:
    """Per directory (Go package / TS folder / C# namespace dir): route constants and env-var names."""

    def __init__(self) -> None:
        self.route_consts: dict[str, str] = {}     # name -> raw path
        self.env_hints: set[str] = set()


def _dir_of(file_path: str) -> str:
    return str(PurePosixPath(file_path).parent)


_HINT_DIRS = ("outbound", "clients", "client", "gateways", "gateway", "integrations", "integration", "external",
              "providers", "provider", "adapters", "services", "service", "apis", "sdk", "connectors")


def _target_hint(file_path: str) -> str:
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


def extract_http(repo: RepoInfo, extractors: list) -> HttpResult:
    """`extractors` are FileExtractor objects (extract.py) after `.run()`."""
    out = HttpResult()
    by_dir: dict[str, _PackageContext] = {}
    for fx in extractors:
        ctx = by_dir.setdefault(_dir_of(fx.file.path), _PackageContext())
        _collect_constants(fx, ctx)
    for fx in extractors:
        if TEST_FILE.search("/" + fx.file.path):
            continue
        ctx = by_dir[_dir_of(fx.file.path)]
        scanner = {"go": _GoScanner, "typescript": _TsScanner, "tsx": _TsScanner, "javascript": _TsScanner,
                   "csharp": _CsScanner, "python": _PyScanner}.get(fx.file.language)
        if scanner is None:
            continue
        try:
            scanner(repo, fx, ctx, out).run()
        except Exception as e:  # noqa: BLE001 — a weird file must not stop the repo
            out.warnings.append(f"{fx.file.path}: http candidates skipped ({type(e).__name__}: {e})")
    _dedupe(out)
    return out


def _dedupe(out: HttpResult) -> None:
    seen: set[str] = set()
    eps = []
    for e in out.endpoints:
        if e.id in seen:
            continue
        seen.add(e.id)
        eps.append(e)
    out.endpoints = eps
    seen.clear()
    calls = []
    for c in out.calls:
        if c.id in seen:
            continue
        seen.add(c.id)
        calls.append(c)
    out.calls = calls


def _collect_constants(fx, ctx: _PackageContext) -> None:
    src = fx.src
    for n in _walk(fx.tree.root_node):
        name = val = None
        if n.type in ("const_spec", "var_spec", "variable_declarator"):           # Go, TS/JS, C#
            name, val = n.child_by_field_name("name"), n.child_by_field_name("value")
            if val is None and n.type == "variable_declarator":                    # C#: identifier + equals_value_clause
                kids = [c for c in n.children if c.is_named]
                if len(kids) >= 2:
                    name, val = kids[0], kids[-1]
        elif n.type == "assignment" and n.parent is not None and n.parent.type in ("module", "expression_statement"):  # Python module-level
            name, val = n.child_by_field_name("left"), n.child_by_field_name("right")
        if name is not None and val is not None and name.type in ("identifier", "property_identifier"):
            lit = _first_string(val, src)
            if lit is not None and (PATH_LITERAL.match(lit) or REL_PATH_LITERAL.match(lit)) and len(lit) > 1:
                ctx.route_consts[_text(name, src)] = lit
        if n.type in STRING_NODES:
            lit = _unquote(_text(n, src))
            if ENV_URL_NAME.match(lit):
                ctx.env_hints.add(lit)


def _first_string(n: Node, src: bytes) -> str | None:
    if n.type in STRING_NODES:
        return _unquote(_text(n, src))
    for c in n.children:
        if c.type in ("call_expression", "invocation_expression", "call"):
            continue                       # don't mine literals out of calls (env("X"), t("key"))
        r = _first_string(c, src)
        if r is not None:
            return r
    return None


def _walk(node: Node):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


# ------------------------------------------------------------------------------------------
class _BaseScanner:
    framework_default = "unknown"

    def __init__(self, repo: RepoInfo, fx, ctx: _PackageContext, out: HttpResult):
        self.repo, self.fx, self.ctx, self.out = repo, fx, ctx, out
        self.src = fx.src
        self.symbols_by_name: dict[str, list[SymbolInfo]] = {}
        for s in fx.symbols:
            self.symbols_by_name.setdefault(s.name, []).append(s)
        self.group_prefix: dict[str, str] = {}   # router/group variable -> path prefix
        self.router_vars: set[str] = set()       # identifiers known to be routers/groups/apps

    def evidence(self, node: Node) -> str:
        return f"{self.repo.name}:{self.fx.file.path}:{node.start_point[0] + 1}"

    # -- template of an interpolated string (Python f"", C# $"", JS `${}`) ------------------
    def _interpolated(self, n: Node) -> str:
        parts = []
        for c in n.children:
            if c.type in ("interpolation", "template_substitution"):
                parts.append("{param}")
            elif c.type in ("string_content", "string_fragment", "interpolated_string_text"):
                parts.append(_text(c, self.src))
            elif c.is_named and c.type not in ("string_start", "string_end", "escape_sequence"):
                parts.append(_text(c, self.src))
            elif c.type == "escape_sequence":
                parts.append(_text(c, self.src))
        raw = "".join(parts) if parts else _unquote(_text(n, self.src))
        return re.sub(r"\{[^}]*\}", "{param}", raw) if n.type == "interpolated_string_expression" else raw

    # -- local variables: `uri := base + "/v1/x"` two lines above the call ----------------------
    _FUNC_NODES = {"function_declaration", "method_declaration", "func_literal", "arrow_function", "function_expression",
                   "method_definition", "function_definition", "local_function_statement", "lambda_expression", "constructor_declaration"}

    def resolve_local(self, ident: Node, depth: int = 0) -> Node | None:
        """Value expression of the closest preceding assignment to this identifier in the enclosing function."""
        if depth > 3:
            return None
        name = _text(ident, self.src)
        scope = ident.parent
        while scope is not None and scope.type not in self._FUNC_NODES:
            scope = scope.parent
        scope = scope or self.fx.tree.root_node
        best: Node | None = None
        for d in _walk(scope):
            if d.start_byte >= ident.start_byte:
                break
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
                    if _text(l, self.src) == name and i < len(rights):
                        best = rights[i]
        return best

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
            lit = self._interpolated(n) if has_interp or t == "interpolated_string_expression" else _unquote(_text(n, src))
            lit = re.sub(r"\$\{[^}]*\}", "{param}", lit)
            m = re.match(r"^\{param\}(/?)(.*)$", lit)              # leading base-URL placeholder
            if m:
                rest = m.group(2)
                if m.group(1) == "/" or (lenient and (_looks_like_rel_path(rest) or re.match(r"^[A-Za-z][A-Za-z0-9_\-]{2,}(\?.*)?$", rest))):
                    lit = "/" + rest.lstrip("/")
                else:
                    return None
            if URL_LITERAL.match(lit) or PATH_LITERAL.match(lit) or REL_PATH_LITERAL.match(lit):
                return lit if len(lit) > 1 else None
            if lenient and _looks_like_rel_path(lit):
                return "/" + lit
            return None
        if t in ("identifier", "selector_expression", "member_expression", "property_identifier", "member_access_expression", "attribute"):
            name = _text(n, src).split(".")[-1]
            if name in self.ctx.route_consts:
                return self.ctx.route_consts[name]
            if t == "identifier":
                val = self.resolve_local(n)
                if val is not None:
                    return self.path_of(val, lenient, _depth + 1)
            return None
        if t in ("binary_expression", "concatenated_string", "binary_operator"):   # base + "/v1/x" + id
            raw = ""
            for c in n.children:
                if not c.is_named:
                    continue
                p = self.path_of(c, lenient, _depth + 1) if c.type not in STRING_NODES else (self._interpolated(c) if any(k.type in ("interpolation", "template_substitution") for k in c.children) else _unquote(_text(c, src)))
                if p is None:
                    if raw:
                        raw += "{param}"
                    continue
                raw += p
            raw = re.sub(r"^\{param\}(?=/)", "", raw)
            if not raw:
                return None
            if raw.startswith("/") or URL_LITERAL.match(raw) or REL_PATH_LITERAL.match(raw):
                return raw
            return ("/" + raw) if lenient and "/" in raw and not raw.startswith("{") else None
        if t in ("call_expression", "invocation_expression", "call"):     # fmt.Sprintf("/v1/%s", id), "...".format(), path.Join
            fn = n.child_by_field_name("function")
            args = n.child_by_field_name("arguments")
            if fn is None:      # C#: invocation_expression children = [member_access|identifier, argument_list]
                kids = [c for c in n.children if c.is_named]
                fn, args = (kids[0] if kids else None), next((c for c in kids if c.type == "argument_list"), None)
            fname = _text(fn, src).split(".")[-1] if fn is not None else ""
            if args is None:
                return None
            arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named]
            if fname in ("Sprintf", "Errorf", "Format", "format"):
                if fname == "format" and fn is not None and fn.type == "attribute":      # "/v1/{}".format(x)
                    recv = fn.child_by_field_name("object")
                    rp = self.path_of(recv, lenient, _depth + 1) if recv is not None else None
                    return rp.replace("{}", "{param}") if rp else None
                return self.path_of(arg_nodes[0], lenient, _depth + 1) if arg_nodes else None
            if fname in ("Join", "JoinPath", "urljoin", "Combine"):
                segs = [self.path_of(a, lenient, _depth + 1) or "{param}" for a in arg_nodes]
                segs = [s for s in segs if s]
                return ("/" + "/".join(s.strip("/") for s in segs)) if segs else None
            return None
        if t in ("parenthesized_expression", "await_expression", "unary_expression"):
            inner = [c for c in n.children if c.is_named]
            return self.path_of(inner[0], lenient, _depth + 1) if inner else None
        if t in ("argument", "keyword_argument"):
            inner = [c for c in n.children if c.is_named]
            return self.path_of(inner[-1], lenient, _depth + 1) if inner else None
        return None

    def _unwrap_arg(self, n: Node) -> Node:
        if n.type == "argument":            # C#: argument -> expression
            inner = [c for c in n.children if c.is_named]
            return inner[-1] if inner else n
        return n

    def method_from_args(self, arg_nodes: list[Node]) -> str | None:
        for a in arg_nodes[:4]:
            txt = _text(a, self.src)
            if a.type in STRING_NODES and _unquote(txt).upper() in HTTP_METHODS:
                return _unquote(txt).upper()
            m = re.match(r"^(?:http\.)?(?:HttpMethod\.)?Method([A-Z][a-z]+)$|^HttpMethod\.([A-Z][a-z]+)$", txt)
            if m:
                v = (m.group(1) or m.group(2) or "").upper()
                if v in HTTP_METHODS:
                    return v
            if a.type in ("object", "composite_literal", "dictionary", "anonymous_object_creation_expression"):
                mm = re.search(r"method\s*[:=]\s*[\"'`]([A-Za-z]+)[\"'`]", txt, re.I)
                if mm and mm.group(1).upper() in HTTP_METHODS:
                    return mm.group(1).upper()
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
        txt = _text(n, self.src)
        if n.type in ("identifier", "selector_expression", "member_expression", "member_access_expression", "attribute"):
            return not txt.lower() in ("nil", "null", "none", "undefined") and not re.search(r"\b(ctx|context|req|request|body|payload|opts|options|params|headers)\b$", txt, re.I)
        if n.type in ("call_expression", "invocation_expression", "call"):
            # http.HandlerFunc(x), middleware(h), wrap(h), timeout(5, h) → handler-ish; fmt.Sprintf/data builders → not
            return not re.search(r"\b(Sprintf|Errorf|Marshal|Join|format|Encode|Serialize|bytes\.|strings\.)", txt)
        return False

    def resolve_handler(self, handler_node: Node | None) -> tuple[str | None, str | None]:
        if handler_node is None:
            return None, None
        node = self._unwrap_arg(handler_node)
        if node.type in HANDLER_NODES:
            return "<inline>", None
        txt = _text(node, self.src).strip()
        m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*\)*\s*$", txt)
        name = m.group(1) if m else None
        if not name or name.lower() in ("nil", "null", "none"):
            return None, None
        cands = [c for c in self.symbols_by_name.get(name) or [] if c.kind in ("function", "method")]
        return name, (cands[0].id if cands else None)

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
            id=ids.http_endpoint(self.repo.tenant, self.repo.name, method or "ANY", path),
            method=method or "ANY", path=path, raw_pattern=raw_pattern, framework=framework,
            file_id=self.fx.file.id, line=node.start_point[0] + 1,
            handler_name=handler_name, handler_id=handler_id, evidence=self.evidence(node),
        ))

    def add_call(self, node: Node, method: str | None, raw_path: str, via: str) -> None:
        path = normalize_path(raw_path)
        if not _has_literal_segment(path):
            return
        caller = self.fx._enclosing_symbol(node)
        self.out.calls.append(HttpCallInfo(
            id=ids.http_call(self.repo.tenant, self.repo.name, self.repo.ref, self.fx.file.path, node.start_point[0] + 1),
            method=(method or "ANY").upper(), path=path, raw_path=raw_path, via=via[-60:],
            target_hint=_target_hint(self.fx.file.path), env_hints=sorted(self.ctx.env_hints),
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


# ------------------------------------------------------------------------------------------
class _GoScanner(_BaseScanner):
    def run(self) -> None:
        for n in _walk(self.fx.tree.root_node):
            if n.type in ("short_var_declaration", "assignment_statement", "var_spec"):
                self._maybe_group(n)
            elif n.type == "call_expression":
                self._call(n)

    def _maybe_group(self, n: Node) -> None:
        left = n.child_by_field_name("left") or n.child_by_field_name("name")
        right = n.child_by_field_name("right") or n.child_by_field_name("value")
        if left is None or right is None:
            return
        rights = [c for c in right.children if c.is_named] if right.type == "expression_list" else [right]
        names = [_text(c, self.src) for c in (left.children if left.type == "expression_list" else [left]) if c.type == "identifier"]
        for r in rights:
            if r.type != "call_expression":
                continue
            fn = r.child_by_field_name("function")
            if fn is None:
                continue
            fname = _text(fn, self.src)
            last = fname.split(".")[-1]
            args = r.child_by_field_name("arguments")
            arg_nodes = [c for c in args.children if c.is_named] if args else []
            if last in GO_MOUNTS:
                self._record_group(names, r, fname, arg_nodes)
            elif last in ("NewServeMux", "NewRouter", "New", "Default", "NewMux") and re.search(r"\b(http|mux|chi|gin|echo|fiber|httprouter)\b", fname):
                for nm in names:
                    self.router_vars.add(nm)

    def _call(self, n: Node) -> None:
        fn = n.child_by_field_name("function")
        args = n.child_by_field_name("arguments")
        if fn is None or args is None:
            return
        callee = _text(fn, self.src)
        name = callee.split(".")[-1]
        recv = callee.rsplit(".", 1)[0] if "." in callee else ""
        recv_last = recv.split(".")[-1]
        arg_nodes = [c for c in args.children if c.is_named]
        if not arg_nodes:
            return

        # ---- exposed routes ---------------------------------------------------------------
        if name in GO_REGISTRARS and len(arg_nodes) >= 2 and not CLIENT_RECEIVER.search(recv_last):
            first = arg_nodes[0]
            raw_first = _unquote(_text(first, self.src)) if first.type in STRING_NODES else None
            lit = raw_first if raw_first and re.match(r"^[A-Z]+ /", raw_first) else self.path_of(first)
            path_idx, method = 0, VERB_BY_NAME.get(name) if name in VERB_BY_NAME else (None if name in ("HandleFunc", "Handle", "Match") else "ANY")
            if name == "Match" and len(arg_nodes) >= 3:                 # gin: r.Match([]string{...}, "/x", h)
                lit, path_idx = self.path_of(arg_nodes[1]), 1
            if lit and (lit.startswith("/") or re.match(r"^[A-Z]+ /", lit)):
                handler = arg_nodes[-1]
                if self.is_handler_like(handler) or recv_last in self.router_vars or name in ("HandleFunc", "Handle"):
                    framework = "net/http"
                    if name in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "Any", "Match"):
                        framework = "gin/echo"
                    elif name in ("Get", "Post", "Put", "Patch", "Delete", "Head", "Options", "All"):
                        framework = "chi/fiber"
                    if method is None:
                        gm = self._gorilla_methods(n)
                        if gm:
                            method, framework = gm, "gorilla"
                    self.add_endpoint(n, method or "ANY", lit, framework, handler, prefix=self.group_prefix.get(recv_last, ""))
                    return

        # ---- outbound calls ---------------------------------------------------------------
        if name in OUTBOUND:
            if name in VERB_BY_NAME and len(arg_nodes) >= 2 and self.is_handler_like(arg_nodes[-1]) and arg_nodes[-1].type not in STRING_NODES:
                return                                                  # unknown router: r.Get("/x", handler)
            if name in GENERIC_OUTBOUND and not CLIENT_RECEIVER.search(recv_last) and not callee.startswith("http."):
                return
            method = OUTBOUND[name] or self.method_from_args(arg_nodes)
            lenient = bool(CLIENT_RECEIVER.search(recv_last)) or callee.startswith("http.")
            for a in arg_nodes:
                p = self.path_of(a, lenient=lenient)
                if p is not None:
                    self.add_call(n, method, p, callee)
                    return

    def _gorilla_methods(self, call: Node) -> str | None:
        """`r.HandleFunc("/x", h).Methods("GET")` — `call` is the operand of `.Methods(...)`."""
        p = call.parent
        if p is None or p.type != "selector_expression":
            return None
        fld = p.child_by_field_name("field")
        if fld is None or _text(fld, self.src) != "Methods":
            return None
        outer = p.parent
        if outer is None or outer.type != "call_expression":
            return None
        args = outer.child_by_field_name("arguments")
        return self.method_from_args([c for c in args.children if c.is_named]) if args else None


# ------------------------------------------------------------------------------------------
class _TsScanner(_BaseScanner):
    """express / koa / fastify (`app.get('/x', handler)`) + NestJS decorators."""

    def run(self) -> None:
        controller_prefix: dict[int, str] = {}
        for n in _walk(self.fx.tree.root_node):
            if n.type == "decorator":
                self._decorator(n, controller_prefix)
            elif n.type in ("variable_declarator", "assignment_expression"):
                self._maybe_router_var(n)
            elif n.type == "call_expression":
                if n.parent is not None and n.parent.type == "decorator":
                    continue
                self._call(n)

    def _maybe_router_var(self, n: Node) -> None:
        name = n.child_by_field_name("name") or n.child_by_field_name("left")
        val = n.child_by_field_name("value") or n.child_by_field_name("right")
        if name is None or val is None or name.type != "identifier":
            return
        txt = _text(val, self.src)
        if re.search(r"\b(express|Router|Fastify|fastify|Koa|new Hono|Hono|new Elysia|Elysia)\s*\(", txt) or re.search(r"\.(Router|router)\(\)", txt):
            self.router_vars.add(_text(name, self.src))

    def _decorator(self, n: Node, controller_prefix: dict[int, str]) -> None:
        txt = _text(n, self.src)
        m = re.match(r"@(Controller|Get|Post|Put|Patch|Delete|Head|Options|All)\s*\(\s*([\"'`]([^\"'`]*)[\"'`])?", txt)
        if not m:
            return
        kind, raw = m.group(1), (m.group(3) or "")
        if kind == "Controller":
            target = n.parent
            if target is not None and target.type == "export_statement":
                target = next((c for c in target.named_children if c.type in ("class_declaration", "class")), target)
            if target is not None:
                controller_prefix[target.id] = "/" + raw.strip("/") if raw else ""
            return
        cls = n.parent
        while cls is not None and cls.type not in ("class_declaration", "class"):
            cls = cls.parent
        prefix = controller_prefix.get(cls.id, "") if cls is not None else ""
        sib = n.next_named_sibling
        while sib is not None and sib.type == "decorator":
            sib = sib.next_named_sibling
        handler_node = sib.child_by_field_name("name") if sib is not None and sib.type in ("method_definition", "public_field_definition") else None
        hname, hid = self.resolve_handler(handler_node) if handler_node is not None else (None, None)
        method = "ANY" if kind == "All" else kind.upper()
        self.add_endpoint(n, method, ("/" + raw.strip("/")) if raw else "/", "nest", None, prefix=prefix, handler_name=hname, handler_id=hid)

    def _call(self, n: Node) -> None:
        fn = n.child_by_field_name("function")
        args = n.child_by_field_name("arguments")
        if fn is None or args is None:
            return
        callee = _text(fn, self.src)
        name = callee.split(".")[-1]
        recv = callee.rsplit(".", 1)[0] if "." in callee else ""
        recv_last = recv.split(".")[-1]
        arg_nodes = [c for c in args.children if c.is_named]
        if not arg_nodes:
            return
        if "getHttpServer" in callee or "supertest" in callee or "request(app" in callee:
            return                                                  # supertest-style test clients
        if name in TS_REGISTRARS and len(arg_nodes) >= 2:
            p = self.path_of(arg_nodes[0])
            if p is not None and p.startswith("/") and (self.is_handler_like(arg_nodes[-1]) or recv_last in self.router_vars) \
                    and not CLIENT_RECEIVER.search(recv_last):
                if name == "route":                                  # app.route('/x').get(h) — take the verb from the chain
                    return
                self.add_endpoint(n, VERB_BY_NAME.get(name, "ANY"), p, "express", arg_nodes[-1])
                return
        if name in OUTBOUND:
            if name in VERB_BY_NAME and len(arg_nodes) >= 2 and self.is_handler_like(arg_nodes[-1]):
                return
            if name in GENERIC_OUTBOUND and not CLIENT_RECEIVER.search(recv_last):
                return
            if name in VERB_BY_NAME and not (CLIENT_RECEIVER.search(recv_last) or recv_last in ("http", "this")):
                return                                                  # cache.get(key), map.delete(k) ...
            method = OUTBOUND[name] or self.method_from_args(arg_nodes)
            lenient = name in ("fetch", "$fetch", "ofetch") or bool(CLIENT_RECEIVER.search(recv_last))
            for a in arg_nodes:
                p = self.path_of(a, lenient=lenient)
                if p is not None:
                    self.add_call(n, method, p, callee)
                    return


# ------------------------------------------------------------------------------------------
class _CsScanner(_BaseScanner):
    """ASP.NET Core: attribute-routed controllers + minimal APIs; HttpClient / Refit outbound."""

    def run(self) -> None:
        for n in _walk(self.fx.tree.root_node):
            if n.type == "class_declaration":
                self._controller(n)
            elif n.type == "interface_declaration":
                self._refit(n)
            elif n.type == "variable_declarator":
                self._maybe_group(n)
            elif n.type == "invocation_expression":
                self._invocation(n)
            elif n.type == "object_creation_expression":
                self._request_message(n)

    # -- helpers ------------------------------------------------------------------------------
    def _attrs(self, n: Node) -> list[tuple[str, str | None, Node]]:
        """(name, first string arg or None, attribute node) for every attribute on a declaration."""
        out = []
        for al in n.children:
            if al.type != "attribute_list":
                continue
            for a in al.children:
                if a.type != "attribute":
                    continue
                nm = next((c for c in a.children if c.type in ("identifier", "qualified_name", "generic_name")), None)
                args = next((c for c in a.children if c.type == "attribute_argument_list"), None)
                lit = None
                if args is not None:
                    first = next((c for c in args.children if c.type == "attribute_argument"), None)
                    if first is not None:
                        s = _first_string(first, self.src)
                        if s is not None and not re.match(r"^(Name|Order)\s*=", _text(first, self.src)):
                            lit = s
                out.append((_text(nm, self.src) if nm is not None else "", lit, a))
        return out

    def _controller(self, cls: Node) -> None:
        prefixes = [lit for name, lit, _ in self._attrs(cls) if name in ("Route", "RoutePrefix") and lit is not None]
        cname = cls.child_by_field_name("name")
        cname_txt = _text(cname, self.src) if cname is not None else ""
        controller = re.sub(r"Controller$", "", cname_txt)
        body = cls.child_by_field_name("body")
        if body is None:
            return
        is_controller = bool(prefixes) or cname_txt.endswith("Controller") or any(name == "ApiController" for name, _, _ in self._attrs(cls))
        if not is_controller:
            return
        prefix = prefixes[0] if prefixes else ""
        for m in body.children:
            if m.type != "method_declaration":
                continue
            attrs = self._attrs(m)
            routes = [(CS_HTTP_ATTR[name], lit, a) for name, lit, a in attrs if name in CS_HTTP_ATTR]
            extra = [lit for name, lit, _ in attrs if name == "Route" and lit is not None]
            if not routes:
                continue
            mname = m.child_by_field_name("name")
            hname = _text(mname, self.src) if mname is not None else None
            hid = next((s.id for s in self.symbols_by_name.get(hname or "", []) if s.kind == "method"), None)
            for method, lit, a in routes:
                tmpl = lit if lit is not None else (extra[0] if extra else "")
                full = tmpl if (tmpl.startswith("/") or tmpl.startswith("~/")) else (prefix.rstrip("/") + "/" + tmpl).rstrip("/")
                full = full.replace("~/", "/")
                full = re.sub(r"\[controller\]", controller.lower(), full, flags=re.I)
                full = re.sub(r"\[action\]", (hname or "").lower(), full, flags=re.I)
                self.add_endpoint(a, method, full or "/", "aspnet", None, handler_name=hname, handler_id=hid)

    def _refit(self, iface: Node) -> None:
        body = iface.child_by_field_name("body")
        if body is None:
            return
        for m in body.children:
            if m.type != "method_declaration":
                continue
            for name, lit, a in self._attrs(m):
                if name in ("Get", "Post", "Put", "Patch", "Delete", "Head") and lit is not None:
                    self.add_call(a, VERB_BY_NAME[name], lit, "refit")

    def _maybe_group(self, n: Node) -> None:
        kids = [c for c in n.children if c.is_named]
        if len(kids) < 2 or kids[0].type != "identifier":
            return
        val = kids[-1]
        if val.type == "equals_value_clause":
            inner = [c for c in val.children if c.is_named]
            val = inner[-1] if inner else val
        if val.type != "invocation_expression":
            return
        txt = _text(val, self.src)
        if ".MapGroup" in txt:
            grp = None
            for d in _walk(val):
                if d.type != "invocation_expression":
                    continue
                callee = next((c for c in d.children if c.is_named), None)
                if callee is not None and callee.type != "argument_list" and _text(callee, self.src).endswith("MapGroup"):
                    grp = d                    # pre-order: the deepest (innermost) MapGroup wins
            if grp is not None:
                args = next((c for c in grp.children if c.type == "argument_list"), None)
                arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named] if args else []
                fn_text = _text(grp, self.src).split("(")[0]
                self._record_group([_text(kids[0], self.src)], grp, fn_text, arg_nodes)
        elif re.search(r"\b(WebApplication|CreateBuilder|Build)\s*\(", txt):
            self.router_vars.add(_text(kids[0], self.src))

    def _invocation(self, n: Node) -> None:
        kids = [c for c in n.children if c.is_named]
        if len(kids) < 2 or kids[-1].type != "argument_list":
            return
        fn, args = kids[0], kids[-1]
        callee = _text(fn, self.src)
        callee = re.sub(r"<[^<>]*>", "", callee)                   # GetFromJsonAsync<T>
        name = callee.split(".")[-1]
        recv_last = (callee.rsplit(".", 1)[0] if "." in callee else "").split(".")[-1]
        arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named]
        if not arg_nodes:
            return
        if name in CS_MAP and len(arg_nodes) >= 2:
            p = self.path_of(arg_nodes[0])
            if p is not None and (self.is_handler_like(arg_nodes[-1]) or True):
                method = CS_MAP[name]
                if name == "MapMethods":
                    method = self.method_from_args(arg_nodes[1:2]) or "ANY"
                self.add_endpoint(n, method or "ANY", p, "aspnet-minimal", arg_nodes[-1], prefix=self.group_prefix.get(recv_last, ""))
                return
        if name in OUTBOUND and name.endswith("Async"):
            method = OUTBOUND.get(name) or self.method_from_args(arg_nodes)
            for a in arg_nodes:
                p = self.path_of(a, lenient=True)
                if p is not None:
                    self.add_call(n, method, p, callee)
                    return

    def _request_message(self, n: Node) -> None:
        txt = _text(n, self.src)
        if "HttpRequestMessage" not in txt:
            return
        args = next((c for c in n.children if c.type == "argument_list"), None)
        arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named] if args else []
        method = self.method_from_args(arg_nodes)
        for a in arg_nodes:
            p = self.path_of(a, lenient=True)
            if p is not None:
                self.add_call(n, method, p, "new HttpRequestMessage")
                return


# ------------------------------------------------------------------------------------------
class _PyScanner(_BaseScanner):
    """FastAPI / Flask / Starlette decorators; requests / httpx / aiohttp outbound."""

    def run(self) -> None:
        for n in _walk(self.fx.tree.root_node):
            if n.type == "assignment":
                self._maybe_router(n)
        for n in _walk(self.fx.tree.root_node):
            if n.type == "decorated_definition":
                self._decorated(n)
            elif n.type == "call":
                if n.parent is not None and n.parent.type == "decorator":
                    continue
                self._call(n)

    def _maybe_router(self, n: Node) -> None:
        left, right = n.child_by_field_name("left"), n.child_by_field_name("right")
        if left is None or right is None or left.type != "identifier" or right.type != "call":
            return
        fn = right.child_by_field_name("function")
        fname = _text(fn, self.src).split(".")[-1] if fn is not None else ""
        if fname in ("APIRouter", "Blueprint", "FastAPI", "Flask", "Starlette", "Router", "Sanic", "Quart"):
            name = _text(left, self.src)
            self.router_vars.add(name)
            args = right.child_by_field_name("arguments")
            prefix = ""
            if args is not None:
                for a in args.children:
                    if a.type == "keyword_argument" and _text(a.child_by_field_name("name"), self.src) in ("prefix", "url_prefix"):
                        v = a.child_by_field_name("value")
                        prefix = _unquote(_text(v, self.src)) if v is not None and v.type == "string" else ""
            self.group_prefix[name] = prefix

    def _decorated(self, n: Node) -> None:
        func = next((c for c in n.children if c.type in ("function_definition", "class_definition")), None)
        fname_node = func.child_by_field_name("name") if func is not None else None
        hname = _text(fname_node, self.src) if fname_node is not None else None
        hid = next((s.id for s in self.symbols_by_name.get(hname or "", []) if s.kind in ("function", "method")), None)
        for d in n.children:
            if d.type != "decorator":
                continue
            call = next((c for c in d.children if c.type == "call"), None)
            if call is None:
                continue
            fn = call.child_by_field_name("function")
            args = call.child_by_field_name("arguments")
            if fn is None or args is None or fn.type != "attribute":
                continue
            recv = _text(fn.child_by_field_name("object"), self.src).split(".")[-1]
            verb = _text(fn.child_by_field_name("attribute"), self.src)
            if verb not in PY_REGISTRARS:
                continue
            arg_nodes = [c for c in args.children if c.is_named]
            if not arg_nodes:
                continue
            p = self.path_of(arg_nodes[0]) if arg_nodes[0].type == "string" else None
            if p is None or not p.startswith("/"):
                continue
            methods = [VERB_BY_NAME[verb]] if verb in VERB_BY_NAME else ["ANY"]
            if verb in ("route", "api_route"):
                for a in arg_nodes:
                    if a.type == "keyword_argument" and _text(a.child_by_field_name("name"), self.src) == "methods":
                        found = re.findall(r"[\"']([A-Za-z]+)[\"']", _text(a.child_by_field_name("value"), self.src))
                        methods = [m.upper() for m in found if m.upper() in HTTP_METHODS] or ["ANY"]
                if verb == "route" and methods == ["ANY"]:
                    methods = ["GET"]                     # Flask default
            if verb == "websocket":
                continue
            framework = "flask" if verb == "route" or recv in ("bp", "blueprint") else "fastapi"
            for m in methods:
                self.add_endpoint(d, m, p, framework, None, prefix=self.group_prefix.get(recv, ""), handler_name=hname, handler_id=hid)

    def _call(self, n: Node) -> None:
        fn = n.child_by_field_name("function")
        args = n.child_by_field_name("arguments")
        if fn is None or args is None or fn.type != "attribute":
            return
        callee = _text(fn, self.src)
        name = callee.split(".")[-1]
        recv_last = callee.rsplit(".", 1)[0].split(".")[-1]
        if name not in OUTBOUND or name not in VERB_BY_NAME and name != "request":
            return
        if recv_last in self.router_vars or recv_last in ("app", "router", "bp", "blueprint", "api"):
            return                                                  # app.get(...) used imperatively
        if not (CLIENT_RECEIVER.search(recv_last) or recv_last in ("requests", "httpx", "session", "client", "urllib3", "http")):
            return
        arg_nodes = [c for c in args.children if c.is_named]
        method = OUTBOUND.get(name) or self.method_from_args(arg_nodes)
        for a in arg_nodes:
            if a.type == "keyword_argument":
                if _text(a.child_by_field_name("name"), self.src) not in ("url", "path"):
                    continue
                a = a.child_by_field_name("value")
            p = self.path_of(a, lenient=True)
            if p is not None:
                self.add_call(n, method, p, callee)
                return
