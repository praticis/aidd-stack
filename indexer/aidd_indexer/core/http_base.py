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
Test files and e2e/integration folders are skipped. Paths made only of placeholders are dropped.
Every candidate carries evidence `repo:path:line`; the linker (F0.5) decides which endpoint a call
hits — here we only record what the code says.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from tree_sitter import Node

from ..languages.base import node_text as text, walk
from . import ids
from .model import HttpCallInfo, HttpEndpointInfo, RepoInfo, SymbolInfo
from .paths import (ENV_URL_NAME, HTTP_METHODS, PATH_LITERAL, REL_PATH_LITERAL, URL_LITERAL, VERB_BY_NAME,
                    has_literal_segment, looks_like_rel_path, normalize_path, unquote)


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

TEST_FILE = re.compile(r"(_test\.go$|\.spec\.[tj]sx?$|\.test\.[tj]sx?$|(^|/)test_[^/]*\.py$|_test\.py$|conftest\.py$|"
                       r"Tests?\.cs$|/tests?/|/testdata/|/mocks?/|/e2e/|/integration[-_]tests?/|/__tests__/|\.Tests?/|/testing/)")
STRING_NODES = {"interpreted_string_literal", "raw_string_literal", "string", "string_literal", "template_string",
                "verbatim_string_literal", "interpolated_string_expression"}
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

    def __init__(self) -> None:
        self.route_consts: dict[str, str] = {}     # name -> raw path
        self.env_hints: set[str] = set()


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

def collect_constants(fx, ctx: PackageContext) -> None:
    src = fx.src
    for n in walk(fx.tree.root_node):
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
            lit = first_string(val, src)
            if lit is not None and (PATH_LITERAL.match(lit) or REL_PATH_LITERAL.match(lit)) and len(lit) > 1:
                ctx.route_consts[text(name, src)] = lit
        if n.type in STRING_NODES:
            lit = unquote(text(n, src))
            if ENV_URL_NAME.match(lit):
                ctx.env_hints.add(lit)


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

    def __init__(self, repo: RepoInfo, fx, ctx: PackageContext, out: HttpResult):
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
            elif c.type in ("string_content", "string_fragment", "interpolated_string_text", "escape_sequence"):
                parts.append(text(c, self.src))
            # interpolation_start ($"), string_start/end, quotes: structural, no text
        raw = "".join(parts) if parts else unquote(text(n, self.src))
        return re.sub(r"\{[^}]*\}", "{param}", raw) if n.type == "interpolated_string_expression" else raw

    # -- local variables: `uri := base + "/v1/x"` two lines above the call ----------------------
    _FUNC_NODES = {"function_declaration", "method_declaration", "func_literal", "arrow_function", "function_expression",
                   "method_definition", "function_definition", "local_function_statement", "lambda_expression", "constructor_declaration"}

    def resolve_local(self, ident: Node, depth: int = 0) -> Node | None:
        """Value expression of the closest preceding assignment to this identifier in the enclosing function."""
        if depth > 3:
            return None
        name = text(ident, self.src)
        scope = ident.parent
        while scope is not None and scope.type not in self._FUNC_NODES:
            scope = scope.parent
        scope = scope or self.fx.tree.root_node
        best: Node | None = None
        for d in walk(scope):
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
                    if text(l, self.src) == name and i < len(rights):
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
            lit = self._interpolated(n) if has_interp or t == "interpolated_string_expression" else unquote(text(n, src))
            lit = re.sub(r"\$\{[^}]*\}", "{param}", lit)
            m = re.match(r"^\{param\}(/?)(.*)$", lit)              # leading base-URL placeholder
            if m:
                rest = m.group(2)
                if m.group(1) == "/" or (lenient and (looks_like_rel_path(rest) or re.match(r"^[A-Za-z][A-Za-z0-9_\-]{2,}(\?.*)?$", rest))):
                    lit = "/" + rest.lstrip("/")
                else:
                    return None
            if URL_LITERAL.match(lit) or PATH_LITERAL.match(lit) or REL_PATH_LITERAL.match(lit):
                return lit if len(lit) > 1 else None
            if lenient and looks_like_rel_path(lit):
                return "/" + lit
            return None
        if t in ("identifier", "selector_expression", "member_expression", "property_identifier", "member_access_expression", "attribute"):
            name = text(n, src).split(".")[-1]
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
                p = self.path_of(c, lenient, _depth + 1) if c.type not in STRING_NODES else (self._interpolated(c) if any(k.type in ("interpolation", "template_substitution") for k in c.children) else unquote(text(c, src)))
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
                segs = [self.path_of(a, lenient, _depth + 1) or "{param}" for a in arg_nodes]
                segs = [s for s in segs if s]
                return ("/" + "/".join(s.strip("/") for s in segs)) if segs else None
            return None
        if t == "object_creation_expression":             # new Uri("api/x", UriKind.Relative)
            if "Uri" in text(n, src).split("(")[0]:
                args = next((c for c in n.children if c.type == "argument_list"), None)
                arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named] if args else []
                return self.path_of(arg_nodes[0], lenient, _depth + 1) if arg_nodes else None
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
            txt = text(a, self.src)
            if a.type in STRING_NODES and unquote(txt).upper() in HTTP_METHODS:
                return unquote(txt).upper()
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
        txt = text(n, self.src)
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
        txt = text(node, self.src).strip()
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

