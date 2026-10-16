"""C# / ASP.NET Core: attribute-routed controllers (with the `[Route]` of their base class, one level), endpoint
classes (FastEndpoints, Ardalis.ApiEndpoints) and minimal APIs (MapGroup chains); HttpClient.*Async,
HttpRequestMessage, Refit, Flurl, RestSharp outbound."""

from __future__ import annotations

import re
from dataclasses import replace

from tree_sitter import Node

from ...core.http_base import (BaseScanner, HttpResult, OUTBOUND, Pending, STRING_NODES, first_string, rebased,
                               replace_endpoints, split_callee, text, valid_path, walk)
from ...core.http_nodes import CLASS_NODES, CONCAT_NODES, INTERPOLATION_NODES, STRING_TEXT_NODES, has_interpolation
from ...core.http_scope import enclosing_function
from ...core.model import RepoInfo
from ...core import ids
from ...core.paths import HTTP_METHODS, VERB_BY_NAME, has_literal_segment, normalize_path, path_key, unquote

CS_MAP = {"MapGet": "GET", "MapPost": "POST", "MapPut": "PUT", "MapPatch": "PATCH", "MapDelete": "DELETE", "MapMethods": None, "Map": "ANY"}
CS_HTTP_ATTR = {"HttpGet": "GET", "HttpPost": "POST", "HttpPut": "PUT", "HttpPatch": "PATCH", "HttpDelete": "DELETE", "HttpHead": "HEAD", "HttpOptions": "OPTIONS"}
ENDPOINT_BASE = re.compile(r"^(EndpointBase(Sync|Async)?|BaseEndpoint|BaseAsyncEndpoint)$")   # Ardalis.ApiEndpoints
FAST_ENDPOINT = re.compile(r"^(Endpoint|EndpointWithoutRequest|EndpointWithMapping|EndpointWithMapper|Ep)$")
FE_VERBS = {"Get": "GET", "Post": "POST", "Put": "PUT", "Patch": "PATCH", "Delete": "DELETE", "Head": "HEAD", "Options": "OPTIONS"}
FLURL_VERBS = {"GetAsync": "GET", "GetJsonAsync": "GET", "GetStringAsync": "GET", "GetStreamAsync": "GET",
               "PostAsync": "POST", "PostJsonAsync": "POST", "PostStringAsync": "POST", "PostUrlEncodedAsync": "POST",
               "PutAsync": "PUT", "PutJsonAsync": "PUT", "PatchAsync": "PATCH", "PatchJsonAsync": "PATCH",
               "DeleteAsync": "DELETE", "HeadAsync": "HEAD", "OptionsAsync": "OPTIONS"}


class CsScanner(BaseScanner):
    """ASP.NET Core: attribute-routed controllers + minimal APIs; HttpClient / Refit outbound."""
    relative_on_groups = True

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self._types: dict[int, dict[str, str | None]] = {}             # function → its names' declared types
        self._class_members: dict[int, dict[str, str]] = {}            # class node → its members' types

    def run(self) -> None:
        if b"NSwag toolchain" in self.src[:4096]:           # a generated client: each operation, read whole
            for n in walk(self.fx.tree.root_node):
                if n.type == "method_declaration":
                    self._nswag_operation(n)
            return
        for n in walk(self.fx.tree.root_node):
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
                        s = first_string(first, self.src)
                        if s is not None and not re.match(r"^(Name|Order)\s*=", text(first, self.src)):
                            lit = s
                out.append((text(nm, self.src) if nm is not None else "", lit, a))
        return out

    def _bases(self, cls: Node) -> list[str]:
        """The base types as dotted names without type arguments: `Endpoint<Req, Res>` → `Endpoint`,
        `EndpointBaseAsync.WithRequest<R>.WithActionResult<T>` → `EndpointBaseAsync.WithRequest.WithActionResult`."""
        bl = next((c for c in cls.children if c.type == "base_list"), None)
        out = []
        for b in (c for c in bl.children if c.is_named) if bl is not None else ():
            name = re.sub(r"\s+", "", text(b, self.src)).split("(")[0]
            while re.search(r"<[^<>]*>", name):
                name = re.sub(r"<[^<>]*>", "", name)
            out.append(name.removeprefix("global::"))
        return out

    def _controller(self, cls: Node) -> None:
        attrs = self._attrs(cls)
        prefixes = [lit for name, lit, _ in attrs if name in ("Route", "RoutePrefix") and lit is not None]
        cname = cls.child_by_field_name("name")
        cname_txt = text(cname, self.src) if cname is not None else ""
        bases = self._bases(cls)
        if cname_txt:                              # what a derived controller in another file inherits
            partial = any(c.type == "modifier" and text(c, self.src) == "partial" for c in cls.children)
            self.out.publish("cs.class", cname_txt, (tuple(prefixes), partial))
        controller = re.sub(r"Controller$", "", cname_txt)
        body = cls.child_by_field_name("body")
        if body is None or self._fast_endpoint(cls, body, bases):
            return
        names = {name for name, _, _ in attrs}
        segments = {seg for b in bases for seg in b.split(".")}
        is_controller = "NonController" not in names and (
            bool(prefixes) or cname_txt.endswith("Controller") or bool(names & {"ApiController", "Controller"})
            or any(b.split(".")[-1].endswith(("Controller", "ControllerBase")) for b in bases)
            or any(ENDPOINT_BASE.match(seg) for seg in segments))
        if not is_controller:
            return
        prefix = prefixes[0] if prefixes else ""
        area = next((lit for name, lit, _ in attrs if name == "Area" and lit), "")
        inherit = not prefixes and bool(bases)     # no [Route] of its own: the base class's, if it has one
        abstract = any(c.type == "modifier" and text(c, self.src) == "abstract" for c in cls.children)
        own: set[str] = set()
        for m in body.children:
            if m.type != "method_declaration":
                continue
            attrs = self._attrs(m)
            routes = [(CS_HTTP_ATTR[name], lit, a) for name, lit, a in attrs if name in CS_HTTP_ATTR]
            extra = [lit for name, lit, _ in attrs if name == "Route" and lit is not None]
            if not routes:
                continue
            mname = m.child_by_field_name("name")
            hname = text(mname, self.src) if mname is not None else None
            hid = next((s.id for s in self.symbols_by_name.get(hname or "", []) if s.kind == "method"), None)
            own.add(hname or "")
            for method, lit, a in routes:
                tmpl = lit if lit is not None else (extra[0] if extra else "")
                absolute = tmpl.startswith(("/", "~/"))
                if cname_txt:                   # what a derived controller in another file takes, under its own route
                    self.out.publish("cs.actions", cname_txt,
                                     (self.endpoint_info(a, method, "/", "aspnet", hname, hid), tmpl, absolute, hname or ""))
                if abstract:
                    continue                    # not routable by itself: its actions live under each derived controller
                if not prefixes and not tmpl and not inherit:
                    continue                    # conventional routing ({controller}/{action}): no path of its own here
                full = tmpl if absolute else (prefix.rstrip("/") + "/" + tmpl).rstrip("/")
                full = _tokens(full.replace("~/", "/"), controller, hname or "", area)
                ep = self.add_endpoint(a, method, full or "/", "aspnet", None, handler_name=hname, handler_id=hid)
                if inherit and not absolute and ep is not None:
                    self.out.pending.append(Pending(ep, "cs.inherited-route",
                                                    (tuple(b.split(".")[-1] for b in bases), controller, hname or "", not tmpl, area)))
        if bases and not abstract:                  # the actions its base declares are routes of this controller too
            self.out.pending.append(Pending(None, "cs.inherited-actions",
                                            (tuple(b.split(".")[-1] for b in bases), controller, tuple(prefixes), area, frozenset(own))))

    def _fast_endpoint(self, cls: Node, body: Node, bases: list[str]) -> bool:
        """FastEndpoints: a class deriving from `Endpoint<...>` (`EndpointWithoutRequest`, `Ep.Req<..>.Res<..>`) that
        declares its routes in `Configure()` — `Get("/x")`, `Post(CreateRequest.Route)`, `Verbs(Http.POST)` +
        `Routes("/x")`; the handler is its `HandleAsync`/`ExecuteAsync`."""
        if not any(FAST_ENDPOINT.match(seg) for b in bases for seg in b.split(".")):
            return False
        methods = {text(m.child_by_field_name("name"), self.src): m for m in body.children
                   if m.type == "method_declaration" and m.child_by_field_name("name") is not None}
        configure = methods.get("Configure")
        if configure is None:
            return False
        hname = next((n for n in ("HandleAsync", "ExecuteAsync") if n in methods), None)
        first, last = cls.start_point[0] + 1, cls.end_point[0] + 1
        hid = next((s.id for s in self.symbols_by_name.get(hname or "", [])
                    if s.kind == "method" and first <= s.line_start <= last), None)
        verbs: list[str] = []
        for d in walk(configure):
            kids = [c for c in d.children if c.is_named] if d.type == "invocation_expression" else []
            if len(kids) < 2 or kids[0].type != "identifier" or kids[-1].type != "argument_list":
                continue                        # only the endpoint's own calls: `Get(...)`, not `s.Get(...)`
            name = text(kids[0], self.src)
            args = [self._unwrap_arg(c) for c in kids[-1].children if c.is_named]
            if name == "Verbs":
                verbs = [v for a in args if (v := re.sub(r"^Http\.", "", unquote(text(a, self.src))).upper()) in HTTP_METHODS]
                continue
            methods_here = [FE_VERBS[name]] if name in FE_VERBS else verbs if name == "Routes" else []
            for a in args:
                p = self.path_of(a)
                for method in methods_here if p is not None else ():
                    self.add_endpoint(d, method, p, "fastendpoints", None, handler_name=hname, handler_id=hid)
        return True

    @classmethod
    def compose(cls, out: HttpResult, repo: RepoInfo, view=None) -> None:
        """What crosses files in C#: calls to the repo's own client wrappers (`_compose_wrapped_calls`), and the
        `[Route]` a controller without one of its own takes from its base class (`[Route("[controller]")]` on
        `BaseApiController`), one level up: the base is found by name in the repo — two classes with that name (not
        `partial` halves of one) give nothing. An action with no template is a route only under that prefix."""
        cls._compose_wrapped_calls(out)
        classes = out.facts.get("cs.class", {})
        plan = {}
        for p in out.pending:
            if p.rule != "cs.inherited-route":
                continue
            bases, controller, action, root, area = p.key
            route = _inherited_route(classes, bases)
            if route is not None:
                plan[id(p.item)] = [rebased(repo, p.item, _tokens(route, controller, action, area))]
            elif root:
                plan[id(p.item)] = []
        replace_endpoints(out, plan)
        cls._compose_inherited_actions(out, repo, classes)

    @staticmethod
    def _compose_inherited_actions(out: HttpResult, repo: RepoInfo, classes: dict[str, list]) -> None:
        """`EmailTemplatesController : ChannelTemplatesController<T, TDto>` with `[Route("api/apps/{appId}/email-templates")]`
        and no action of its own: the actions the base declares (one level up, found by name, as the `[Route]`) are its
        routes, under its route — or the one it inherits — with `[controller]` its name. An action it redeclares is its
        own; a base two classes share the name of gives nothing."""
        actions = out.facts.get("cs.actions", {})
        for p in out.pending:
            if p.rule != "cs.inherited-actions":
                continue
            bases, controller, prefixes, area, own = p.key
            base = next((b for b in bases if b in classes), None)
            if base is None or sum(1 for _, partial in classes[base] if not partial) > 1 or base not in actions:
                continue
            route = prefixes[0] if prefixes else _inherited_route(classes, bases)
            if route is None:
                continue
            for proto, tmpl, absolute, action in actions[base]:
                if action in own:
                    continue
                full = tmpl if absolute else (route.rstrip("/") + "/" + tmpl).rstrip("/")
                path = normalize_path(_tokens(full.replace("~/", "/"), controller, action, area) or "/")
                out.endpoints.append(replace(proto, path=path, raw_pattern=tmpl or "/",
                                             id=ids.http_endpoint(repo.tenant, repo.name, proto.method, path_key(path))))

    @staticmethod
    def _compose_wrapped_calls(out: HttpResult) -> None:
        """A call to a client wrapper (`HttpService.HttpGet(uri)`, found by the receiver's declared type) is an
        outbound call: the wrapper's verb, its text around the argument that is the path. A name two wrappers of that
        type define differently (overloads) gives nothing."""
        wrappers = out.facts.get("cs.client-wrapper", {})
        for p in out.pending:
            if p.rule != "cs.client-wrapper":
                continue
            rtype, name, args = p.key
            shapes = set(wrappers.get(f"{rtype}.{name}", ()))
            if len(shapes) != 1:
                continue
            idx, before, after, method = next(iter(shapes))
            raw = valid_path(before + args[idx] + after, lenient=True) if idx < len(args) and args[idx] else None
            path = normalize_path(raw) if raw else ""
            if raw and has_literal_segment(path):
                out.calls.append(replace(p.item, method=method, path=path, raw_path=raw, via=f"{rtype}.{name}"[-60:]))

    def _refit(self, iface: Node) -> None:
        body = iface.child_by_field_name("body")
        if body is None:
            return
        for m in body.children:
            if m.type != "method_declaration":
                continue
            for name, lit, a in self._attrs(m):
                if name in ("Get", "Post", "Put", "Patch", "Delete", "Head", "Options") and lit is not None:
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
        txt = text(val, self.src)
        if ".MapGroup" in txt:
            grp = None
            for d in walk(val):
                if d.type != "invocation_expression":
                    continue
                callee = next((c for c in d.children if c.is_named), None)
                if callee is not None and callee.type != "argument_list" and text(callee, self.src).endswith("MapGroup"):
                    grp = d                    # pre-order: the deepest (innermost) MapGroup wins
            if grp is not None:
                args = next((c for c in grp.children if c.type == "argument_list"), None)
                arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named] if args else []
                fn_text = text(grp, self.src).split("(")[0]
                self._record_group([text(kids[0], self.src)], grp, fn_text, arg_nodes)
        elif re.search(r"\b(WebApplication|CreateBuilder|Build)\s*\(", txt):
            self.router_vars.add(text(kids[0], self.src))
            self.mark_app(text(kids[0], self.src), n)

    def _invocation(self, n: Node) -> None:
        kids = [c for c in n.children if c.is_named]
        if len(kids) < 2 or kids[-1].type != "argument_list":
            return
        fn, args = kids[0], kids[-1]
        callee = self.callee_of(fn)
        while "<" in callee and re.search(r"<[^<>]*>", callee):   # GetFromJsonAsync<T>, GetFromJsonAsync<List<T>>
            callee = re.sub(r"<[^<>]*>", "", callee)
        name, _, recv_last = split_callee(callee)
        arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named]
        if self.convention_call(n, name, recv_last, callee, arg_nodes):
            return
        # Flurl: the *receiver* is the URL — "api/x".GetJsonAsync(), url.AppendPathSegment("orders").PostJsonAsync(body)
        if name in FLURL_VERBS and fn.type == "member_access_expression":
            kids_fn = [c for c in fn.children if c.is_named]
            recv_node = kids_fn[0] if kids_fn else None
            p = self._flurl_path(recv_node) if recv_node is not None else None
            if p is not None:
                self.add_call(n, FLURL_VERBS[name], p, "flurl." + name)
                return
        if not arg_nodes:
            return
        if name in CS_MAP and len(arg_nodes) >= 2:
            p = self.route_path(arg_nodes[0], recv_last, n)
            if p is not None and (self.is_handler_like(arg_nodes[-1]) or True):
                method = CS_MAP[name]
                if name == "MapMethods":
                    method = self.method_from_args(arg_nodes[1:2]) or "ANY"
                self.add_endpoint(n, method or "ANY", p, "aspnet-minimal", arg_nodes[-1], router=recv_last)
                return
        if name in OUTBOUND and name.endswith("Async"):
            if name == "SendAsync" and arg_nodes and arg_nodes[0].type == "identifier":
                val = self.resolve_local(arg_nodes[0])
                if val is not None and val.type == "object_creation_expression" and "HttpRequestMessage" in text(val, self.src):
                    return                                  # recorded at `new HttpRequestMessage(...)`
            method = OUTBOUND.get(name) or self.method_from_args(arg_nodes)
            for a in arg_nodes:
                p = self.path_of(a, lenient=True)
                if p is not None:
                    self.add_call(n, method, p, callee)
                    return
            self._wrapper(n, method, arg_nodes)
            return
        self._wrapped_call(n, fn, name, arg_nodes)

    # -- NSwag-generated clients (H2-D9) ----------------------------------------------------------------------
    def _nswag_operation(self, m: Node) -> None:
        """One operation of an NSwag client: the path template from `// Operation Path: "api/x/{id}"` (v14), else from
        the `urlBuilder_.Append(..)` literals (v13: `Append("api/x/{id}")` + `Replace("{id}", ..)`), the base URL before
        it and the query after `?` left out; the verb from `request_.Method = new HttpMethod("GET")`."""
        body = m.child_by_field_name("body")
        if body is None:
            return
        verb = op_path = None
        appends: list[Node] = []
        for d in walk(body):
            if d.type == "comment" and op_path is None:
                found = re.match(r'//\s*Operation Path:\s*"([^"]*)"', text(d, self.src))
                op_path = found.group(1) if found else None
            elif d.type == "assignment_expression":
                left, right = d.child_by_field_name("left"), d.child_by_field_name("right")
                if left is not None and right is not None and text(left, self.src) == "request_.Method":
                    verb = (first_string(right, self.src) or "").upper() or None
            elif d.type == "invocation_expression":
                kids = [c for c in d.children if c.is_named]
                callee = self.callee_of(kids[0]) if kids else ""
                if callee.startswith("urlBuilder_.") and callee.endswith(".Append") and kids[-1].type == "argument_list":
                    arg = next((self._unwrap_arg(c) for c in kids[-1].children if c.is_named), None)
                    if arg is not None:
                        appends.append(arg)
        if not appends:
            return
        appends.sort(key=lambda a: a.start_byte)
        path = op_path
        if path is None:
            parts: list[str] = []
            for a in appends:
                lit = unquote(text(a, self.src)) if a.type in ("string_literal", "verbatim_string_literal", "character_literal") else None
                if lit is None:
                    if parts:                                   # before the path: the base URL
                        parts.append("{param}")
                    continue
                parts.append(lit.split("?", 1)[0])
                if "?" in lit:
                    break
            path = "".join(parts)
        if verb in HTTP_METHODS and path and valid_path("/" + path.lstrip("/")):
            self.add_call(next((a for a in appends if a.type == "string_literal"), appends[0]), verb,
                          "/" + path.lstrip("/"), "generated-client")

    # -- the repo's own client wrappers: `HttpService.HttpGet<T>(string uri)` and the calls to it --------------
    def _wrapper(self, call: Node, method: str | None, arg_nodes: list[Node]) -> None:
        """`_http.GetAsync($"{_apiUrl}{uri}")` inside `HttpGet<T>(string uri)`: the path is the caller's. Publish the
        method as a client wrapper — which parameter is the path, the verb, what goes around it — under its class and
        the class's bases (a field is often typed by the interface)."""
        m = enclosing_function(call)
        if m is None or m.type != "method_declaration" or m.child_by_field_name("name") is None:
            return
        pl = m.child_by_field_name("parameters")
        params = [text(p.child_by_field_name("name"), self.src) for p in (pl.children if pl is not None else ())
                  if p.type == "parameter" and p.child_by_field_name("name") is not None]
        shape = next((sh for a in arg_nodes if (sh := self._param_shape(a, params)) is not None), None)
        cls = m.parent
        while cls is not None and cls.type not in CLASS_NODES:
            cls = cls.parent
        if shape is None or cls is None or cls.child_by_field_name("name") is None:
            return
        mname = text(m.child_by_field_name("name"), self.src)
        for owner in [text(cls.child_by_field_name("name"), self.src)] + [b.split(".")[-1] for b in self._bases(cls)]:
            self.out.publish("cs.client-wrapper", f"{owner}.{mname}", (*shape, (method or "ANY").upper()))

    def _param_shape(self, a: Node, params: list[str]) -> tuple[int, str, str] | None:
        """(index of the parameter, text before it, text after it) when the path is built around a parameter of the
        method — the first one: `uri`, `$"{_apiUrl}{uri}/{id}"`, `_base + uri`."""
        if a.type == "identifier":
            if text(a, self.src) in params:
                return params.index(text(a, self.src)), "", ""
            a = self.resolve_local(a)
            if a is None:
                return None
        tokens: list[str | int] = []
        if a.type in STRING_NODES and (a.type == "interpolated_string_expression" or has_interpolation(a)):
            for c in a.children:
                if c.type in INTERPOLATION_NODES:
                    inner = [k for k in c.children if k.is_named and k.type != "interpolation_brace"]
                    name = text(inner[0], self.src) if len(inner) == 1 and inner[0].type == "identifier" else None
                    tokens.append(params.index(name) if name in params else "{param}")
                elif c.type in STRING_TEXT_NODES:
                    tokens.append(text(c, self.src))
        elif a.type in CONCAT_NODES:
            stack = [a]
            while stack:
                c = stack.pop()
                if c.type == a.type:
                    stack.extend(reversed([k for k in c.children if k.is_named]))
                elif c.type == "identifier" and text(c, self.src) in params:
                    tokens.append(params.index(text(c, self.src)))
                elif c.type in STRING_NODES and not has_interpolation(c):
                    tokens.append(unquote(text(c, self.src)))
                else:
                    tokens.append(self.path_of(c) or "{param}")
        slots = [i for i, t in enumerate(tokens) if isinstance(t, int)]
        if not slots:
            return None
        i = slots[0]                                  # the path; a later parameter is a placeholder (`{uri}/{id}`)
        around = ("".join(t if isinstance(t, str) else "{param}" for t in tokens[:i]),
                  "".join(t if isinstance(t, str) else "{param}" for t in tokens[i + 1:]))
        return tokens[i], *(re.sub(r"\{[^}]*\}", "{param}", x) for x in around)

    def _wrapped_call(self, n: Node, fn: Node, name: str, arg_nodes: list[Node]) -> None:
        """`_httpService.HttpGet<T>("catalog-items")`: a call on a receiver of a known type with a string argument
        waits for `compose` to find whether that type's method is a client wrapper (it may live in another file)."""
        recv = fn.child_by_field_name("expression") if fn.type == "member_access_expression" else None
        if recv is None or recv.type != "identifier" or not arg_nodes:
            return
        args = tuple(self._literal(a) for a in arg_nodes)
        rtype = self._declared_type(recv, n) if any(args) else None
        if rtype:
            self.out.pending.append(Pending(self.call_info(n, None, "", name), "cs.client-wrapper", (rtype, name, args)))

    def _literal(self, a: Node) -> str | None:
        """Text of a string argument (a template with `{param}`), or of the local it is assigned to."""
        if a.type == "identifier":
            bound, val = self.scopes.binding(a)
            a = val if bound and val is not None else a
        if a.type not in STRING_NODES:
            return None
        return self._interpolated(a, True) if a.type == "interpolated_string_expression" or has_interpolation(a) \
            else unquote(text(a, self.src))

    def _declared_type(self, recv: Node, at: Node) -> str | None:
        """Declared type of a local, parameter, field, property or primary-constructor parameter (simple name): the
        function around `at` first — and, from a lambda or local function, the ones around it — then the class."""
        from .symbols import _CLOSURES, _FUNC_NODES, _enclosing, _members   # the language module imports this one
        name = text(recv, self.src)
        scope = _enclosing(at, _FUNC_NODES)
        while scope is not None:
            types = self._scope_types(scope)
            if name in types:
                return types[name]
            if scope.type not in _CLOSURES:
                break
            scope = _enclosing(scope, _FUNC_NODES)
        cls = at.parent
        while cls is not None and cls.type not in CLASS_NODES:
            cls = cls.parent
        if cls is None:
            return None
        if cls.id not in self._class_members:
            self._class_members[cls.id] = _members(cls, self.src)
        return self._class_members[cls.id].get(name)

    def _scope_types(self, scope: Node) -> dict[str, str | None]:
        """Parameter and local name → declared type (or the type it is created with: `var x = new T()`), read in one
        pass per function."""
        from .symbols import _new_type, _returned_type, _service_type, _type_text
        if scope.id in self._types:
            return self._types[scope.id]
        types: dict[str, str | None] = {}
        for d in walk(scope):
            if d.type != "variable_declaration" or d.parent is None or d.parent.type != "local_declaration_statement":
                continue
            ty = d.child_by_field_name("type") or next((c for c in d.children if c.is_named), None)
            for v in d.children:
                nm = v.child_by_field_name("name") or next((c for c in v.children if c.type == "identifier"), None) \
                    if v.type == "variable_declarator" else None
                if nm is None:
                    continue
                tt = _type_text(ty, self.src)
                if tt is None:
                    init = next((c for c in v.children if c.is_named and c.id != nm.id), None)
                    tt = (_new_type(init, self.src) or _service_type(init, self.src)
                          or _returned_type(init, scope, self.src)) if init is not None else None
                types[text(nm, self.src)] = tt
        pl = scope.child_by_field_name("parameters") or next((c for c in scope.children if c.type == "parameter_list"), None)
        for prm in (pl.children if pl is not None else ()):
            nm = prm.child_by_field_name("name") if prm.type == "parameter" else None
            if nm is not None:
                types[text(nm, self.src)] = _type_text(prm.child_by_field_name("type"), self.src)
        self._types[scope.id] = types
        return types

    def _flurl_path(self, n: Node) -> str | None:
        """URL built by Flurl chaining: base.AppendPathSegment("orders").AppendPathSegment(id).SetQueryParam(...)."""
        segs: list[str] = []
        cur = n
        while cur is not None and cur.type == "invocation_expression":
            kids = [c for c in cur.children if c.is_named]
            if len(kids) < 2 or kids[0].type != "member_access_expression":
                break
            fk = [c for c in kids[0].children if c.is_named]
            mname = text(fk[-1], self.src) if fk else ""
            args = [self._unwrap_arg(c) for c in kids[1].children if c.is_named]
            if mname in ("AppendPathSegment", "AppendPathSegments", "Request"):
                for a in args:
                    lit = unquote(text(a, self.src)) if a.type in STRING_NODES else None
                    segs.insert(0, lit if lit else "{param}")
            elif mname in ("SetQueryParam", "SetQueryParams", "WithHeader", "WithHeaders", "WithOAuthBearerToken", "WithTimeout", "AllowAnyHttpStatus", "WithBasicAuth"):
                pass
            else:
                break
            cur = fk[0] if fk else None
        base = self.path_of(cur, lenient=True) if cur is not None else None
        if base is None and not segs:
            return None
        path = "/".join([base.strip("/")] if base else []) + ("/" + "/".join(segs) if segs else "")
        return ("/" + path.lstrip("/")) if path else None

    def _request_message(self, n: Node) -> None:
        """`new HttpRequestMessage(HttpMethod.Post, "api/x")` and RestSharp `new RestRequest("api/x", Method.Post)`."""
        head = text(n, self.src).split("(")[0]
        if "HttpRequestMessage" not in head and "RestRequest" not in head:
            return
        args = next((c for c in n.children if c.type == "argument_list"), None)
        arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named] if args else []
        method = self.method_from_args(arg_nodes)
        if method is None:                                   # RestSharp: Method.Get / Method.Post
            for a in arg_nodes:
                m = re.match(r"^Method\.([A-Za-z]+)$", text(a, self.src))
                if m and m.group(1).upper() in HTTP_METHODS:
                    method = m.group(1).upper()
        via = "new HttpRequestMessage" if "HttpRequestMessage" in head else "new RestRequest"
        for a in arg_nodes:
            p = self.path_of(a, lenient=True)
            if p is not None:
                self.add_call(n, method, p, via)
                return


def _tokens(path: str, controller: str, action: str, area: str = "") -> str:
    """ASP.NET route tokens as the framework fills them — and as its OpenAPI and the clients generated from it write
    them: `[controller]` is the class name without `Controller`, `[action]` the method name without `Async`
    (`SuppressAsyncSuffixInActionNames`, on by default), `[area]` the controller's `[Area("..")]`. The parameters
    `{controller}`, `{area}`, `{action}` are reserved: the router fixes them to the same values. The framework
    matches without case; so does the linker for these routes."""
    path = re.sub(r"\[controller\]|\{controller\}", lambda _: controller, path, flags=re.I)
    if area:
        path = re.sub(r"\[area\]|\{area\}", lambda _: area, path, flags=re.I)
    return re.sub(r"\[action\]|\{action\}", lambda _: re.sub(r"Async$", "", action), path, flags=re.I)


def _inherited_route(classes: dict[str, list], bases: tuple[str, ...]) -> str | None:
    """The `[Route]` of the first base that is a class of this repo; None when it has none or the name is ambiguous."""
    for b in bases:
        decls = classes.get(b)
        if not decls:
            continue
        if sum(1 for _, partial in decls if not partial) > 1:
            return None
        return next((routes[0] for routes, _ in decls if routes), None)
    return None
