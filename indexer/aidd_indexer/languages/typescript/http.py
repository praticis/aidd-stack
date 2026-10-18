"""TypeScript / JavaScript: express / koa / fastify / Hono (`app.get('/x', handler)`, also chained on the constructor)
+ NestJS decorators (under the package's `setGlobalPrefix`); axios / fetch / got / ky outbound, a request described by
an object (`client.post({ url })`, openapi-ts) and oazapfts' generated client. Routers cross files
through ESM imports and CommonJS `require` / `module.exports` (`global_of`), and through a project's own mount wrappers
(Ghost's `app.lazyUse`) and route wrappers (NodeBB's `setupApiRoute(router, 'get', '/x', .., handler)`)."""

from __future__ import annotations

import re
from dataclasses import replace

from tree_sitter import Node

from ...core.http_base import (BaseScanner, CLIENT_RECEIVER, GENERIC_OUTBOUND, OUTBOUND, HttpResult, Pending, Region,
                               rebased, replace_endpoints, split_callee, text, unwrap_arg, walk)
from ...core import ids
from ...core.http_mounts import APP, TOP, MountedRoot
from ...core.http_nodes import has_interpolation, member
from ...core.model import HttpEndpointInfo, RepoInfo
from ...core.paths import (HTTP_METHODS, PATH_LITERAL, VERB_BY_NAME, is_url_literal, mask_placeholders, normalize_path,
                           path_key, unquote)

TS_REGISTRARS = {"get", "post", "put", "patch", "delete", "head", "options", "all", "route"}
TS_CHAIN_VERBS = {v: VERB_BY_NAME[v] for v in ("get", "post", "put", "patch", "delete", "head", "options")} | {"all": "ANY"}
TS_VERB_ALIASES = {"del": "DELETE"}                                       # superagent, NodeBB's api module
TS_ROUTER_VERBS = {"search": "SEARCH"}               # Express's other verbs: only on a router of the file (directus)
TS_MOUNTS = {"use", "route"}
CHAIN_LINKS = TS_REGISTRARS | TS_MOUNTS | {"mount", "basePath", "on", "notFound", "onError"}   # return the router
ROUTER_CTOR = re.compile(r"\b(express|Router|Fastify|fastify|Koa|Hono|Elysia)\s*(<[^()]*>)?\s*\(|\.(Router|router)\(\)")
WRAPPERS = {"parenthesized_expression", "await_expression", "as_expression", "satisfies_expression",
            "non_null_expression"}
FUNCTIONS = {"function_declaration", "function_expression", "function", "arrow_function", "method_definition",
             "generator_function_declaration"}
OPTIONAL_TAIL = re.compile(r"/:[A-Za-z_$][\w$]*\?$")                     # Express: /reset/:code?
NEST_DECORATORS = {"Controller", "Get", "Post", "Put", "Patch", "Delete", "Head", "Options", "All"}
CONFIG_REQUESTS = {"request", "ajax", "axios"}                            # a request described by an object (`url`)
OAZAPFTS = {"fetchJson", "fetchText", "fetchBlob"}                       # oazapfts.fetchJson<T>(path, opts)
JQUERY = {"$", "jQuery"}
KOA_ROUTERS = ("@koa/router", "koa-router")                              # join a prefix and a path as written
KOA_ROUTER_METHODS = {"routes", "middleware"}                            # `router.routes()`: the router itself
JQUERY_VERBS = {"get": "GET", "post": "POST", "getJSON": "GET"}             # $.get(url, data?, success?)


class TsScanner(BaseScanner):
    """express / koa / fastify / Hono (`app.get('/x', handler)`) + NestJS decorators."""
    mount_rule = "ts.mount"

    def run(self) -> None:
        controller_prefix: dict[int, list[str]] = {}
        self.maybe_mounts: list[tuple] = []        # calls of a method that may be a mount wrapper (`_wrapper_call`)
        self.route_calls: list[tuple] = []         # calls of a function that may be a route wrapper
        self.wrapped: dict[int, str] = {}          # registrations inside a route wrapper → its name (`compose`)
        wraps = b".use(" in self.src
        self.koa_router = any(spec in KOA_ROUTERS for spec, _ in self.imports.values())
        self.koa_mount = {name for name, (spec, orig) in self.imports.items() if spec == "koa-mount" and orig == "default"}
        self.oazapfts = b"generated using oazapfts" in self.src[:1024]
        base = re.search(rb"baseUrl:\s*[\"'](/[^\"']*)[\"']", self.src) if self.oazapfts else None
        self.oazapfts_base = base.group(1).decode().rstrip("/") if base else ""
        for n in walk(self.fx.tree.root_node):
            if n.type == "decorator":
                self._decorator(n, controller_prefix)
            elif n.type in ("variable_declarator", "assignment_expression"):
                self._maybe_router_var(n)
                if n.type == "variable_declarator":
                    self._string_array(n)
            elif n.type == "call_expression":
                if n.parent is not None and n.parent.type == "decorator":
                    continue
                self._call(n)
            if n.type in FUNCTIONS:
                if wraps:
                    self._mount_wrapper(n)
                self._route_wrapper(n)

    def add_endpoint(self, node: Node, method: str, raw_pattern: str, framework: str, handler_node: Node | None,
                     **kw) -> HttpEndpointInfo | None:
        """Express's optional parameters at the end (`/reset/:code?`, `/chats/:roomid?/:index?`): the route answers
        without them too — one route per form."""
        ep = super().add_endpoint(node, method, raw_pattern, framework, handler_node, **kw)
        m = OPTIONAL_TAIL.search(raw_pattern or "")
        if m is not None and not isinstance(raw_pattern, MountedRoot):
            shorter, router = raw_pattern[:m.start()], kw.get("router")
            if not shorter:                                     # the router's root, as `route_path` gives it
                pre = self.prefix_for(router, node) if router is not None else None
                shorter = "/" if router is None or pre or self.is_app(router, node) else MountedRoot("/")
            self.add_endpoint(node, method, shorter, framework, handler_node, **kw)
        return ep

    def route_path(self, n: Node, receiver: str, at: Node) -> str | None:
        """Koa's router (`@koa/router`, `koa-router`) puts the prefix before the path as written: outline's
        `router.post("documents.info", ..)` under `router.use("/", documents.routes())` is `/documents.info`. A path
        without its leading slash on a router of the file is, like a sub-router's root, a route only once a mount
        gives it a prefix (`MountedRoot`); a router mounted nowhere serves nothing at it."""
        p = super().route_path(n, receiver, at)
        if p is not None or not self.koa_router or receiver not in self.router_vars or n.type != "string":
            return p
        lit = unquote(text(n, self.src)).strip()
        return MountedRoot(lit) if lit and PATH_LITERAL.match("/" + mask_placeholders(lit)) else None

    def add_call(self, node: Node, method: str | None, raw_path: str, via: str) -> None:
        """A request on a client with a base (`PackageContext.client_base`) is at the base, joined with a slash as
        axios joins them: docmost's `api.post("/pages/info")` on `axios.create({ baseURL: "/api" })` in another file
        is `/api/pages/info`."""
        base = self._client_base(via) if raw_path and not is_url_literal(raw_path) else None
        if base:
            raw_path = base.rstrip("/") + "/" + raw_path.lstrip("/")
        super().add_call(node, method, raw_path, via)

    def _client_base(self, via: str) -> str | None:
        """The base of the client a call is made on (`_client_of`), when it has a path for one."""
        found = self._client_of(via)
        return found[0].client_base(found[1], found[2]) if found is not None else None

    def _client_of(self, via: str) -> tuple | None:
        """The client a call is made on, as (its directory's context, its file, its name): a module-level client of
        this file (`PackageContext.client_bases`), or an import of one. A client is no router: `api.post("/x", data)`
        is a request whatever its last argument looks like."""
        recv = via.rsplit(".", 1)[0] if "." in via else ""
        if not re.fullmatch(r"[A-Za-z_$][\w$]*", recv):
            return None
        path = self.fx.file.path
        if (path, recv) in self.ctx.client_bases:
            return self.ctx, path, recv
        spec, orig = self.imports.get(recv) or (None, None)
        target = self.resolve_import(spec) if spec is not None and orig is not None else None
        ctx = self.ctx.view.constants(target) if target is not None and self.ctx.view is not None else None
        return (ctx, target, orig) if ctx is not None and (target, orig) in ctx.client_bases else None

    def _maybe_router_var(self, n: Node) -> None:
        name = n.child_by_field_name("name") or n.child_by_field_name("left")
        val = n.child_by_field_name("value") or n.child_by_field_name("right")
        if name is None or val is None or name.type != "identifier":
            return
        txt = text(val, self.src)
        nm = text(name, self.src)
        base = re.search(r"\.basePath\(\s*['\"`]([^'\"`]*)['\"`]\s*\)", txt)      # Hono: new Hono().basePath('/api')
        if base:
            self.router_vars.add(nm)
            src = re.match(r"^([A-Za-z_$][\w$]*)\.basePath", txt)                   # api = app.basePath('/api')
            self.group_prefix[self.group_key(nm, n)] = ((self.prefix_for(src.group(1), n) or "") if src else "").rstrip("/") + base.group(1)
            if src:
                self.mount(nm, n, src.group(1), n, "", derived=True)
            return
        if ROUTER_CTOR.search(txt):                                     # also `new Hono<{ Bindings: Env }>()`
            self.router_vars.add(nm)
            if re.match(r"^(express|fastify|Fastify)\s*\(", txt):           # the application, not an express.Router()
                self.mark_app(nm, n)

    def _mount(self, n: Node, name: str, recv_last: str, arg_nodes: list[Node]) -> bool:
        """express/koa `app.use('/api', router)` or `app.use(router)`, Hono `app.route('/book', book)`: a router under a
        prefix — of this file, or one another file defines (`require('./api')`, an imported `routes`, `routes()`),
        which `compose` follows to that file."""
        if name not in TS_MOUNTS or not recv_last:
            return False
        if name == "use" and len(arg_nodes) == 1 and self.koa_mount:     # koa-mount: app.use(mount("/api", api))
            inner = unwrap_arg(arg_nodes[0])
            f, a = inner.child_by_field_name("function"), inner.child_by_field_name("arguments")
            if inner.type == "call_expression" and f is not None and text(f, self.src) in self.koa_mount and a is not None:
                arg_nodes = [c for c in a.children if c.is_named] or arg_nodes
        p = self.path_of(arg_nodes[0])
        has_path = p is not None and p.startswith("/")
        if name == "route" and (len(arg_nodes) != 2 or not has_path):
            return False                                           # express app.route('/x').get(h)
        if not has_path and name != "use":
            return False
        mounted = False
        for c in (arg_nodes[1:] if has_path else arg_nodes):
            c = self._koa_router(unwrap_arg(c))
            if c.type == "identifier" and text(c, self.src) in self.router_vars:
                self.mount(text(c, self.src), c, recv_last, n, p if has_path else "")
                mounted = True
                continue
            g = self._child_ids(c)[0]
            if g is not None:
                prefix = (self.prefix_for(recv_last, n) or "").rstrip("/") + (p if has_path else "")
                self.foreign.append((g, self.router_key(recv_last, n), prefix))
                mounted = True
        return mounted

    def _koa_router(self, c: Node) -> Node:
        """`documents.routes()`, `router.middleware()` handed to a mount: Koa's router itself."""
        f, a = c.child_by_field_name("function"), c.child_by_field_name("arguments")
        obj, prop = member(f) if c.type == "call_expression" and f is not None else (None, None)
        if obj is None or prop is None or text(prop, self.src) not in KOA_ROUTER_METHODS or a is None \
                or a.named_child_count or not self.koa_router:
            return c
        return obj

    def _chained_route(self, n: Node, arg_nodes: list[Node]) -> bool:
        """express `router.route('/x').get(h).post(h)`: each verb a route on the path of `route`. True when `n` is one
        of those verbs, even with a path this file cannot read."""
        chained = self.route_chain(n, {"route"}, TS_CHAIN_VERBS)
        if chained is None:
            return False
        method, builder, recv = chained
        args = builder.child_by_field_name("arguments")
        if args is None or args.named_child_count != 1:
            return False                                           # Hono's app.route('/x', sub) is a mount
        recv_last = self.callee_of(recv).split(".")[-1]
        if recv.type not in ("identifier", "member_expression") \
                or (recv_last not in self.router_vars and CLIENT_RECEIVER.search(recv_last)):
            return True
        p = self.route_path(args.named_children[0], recv_last, n)
        if p is not None and p.startswith("/"):
            self.add_endpoint(n, method, p, "express", arg_nodes[-1], router=recv_last)
        return True

    def _chain_router(self, obj: Node) -> str | None:
        """The router a chain of calls is made on — `new Hono().get(..).route(..)`, `Router().use(a)`: the name the
        chain is bound to (`default` for `export default` and `module.exports =`); `app.get(..).post(..)`: the router
        variable it starts from. None for any other receiver."""
        root = obj
        while root.type == "call_expression":
            inner, link = member(root.child_by_field_name("function"))
            if inner is None or link is None or text(link, self.src) not in CHAIN_LINKS:
                break
            root = inner
        if root.type == "identifier" and text(root, self.src) in self.router_vars:
            return text(root, self.src)
        if root.type not in ("call_expression", "new_expression") or not ROUTER_CTOR.search(text(root, self.src)):
            return None
        owner = self._owner(obj)
        if owner is not None:
            self.router_vars.add(owner)
        return owner

    def _owner(self, n: Node) -> str | None:
        """The name the expression around `n` (its whole chain of calls) is bound to: a variable, `default` for the
        module's default export, `x` for `exports.x =`."""
        top = n
        while top.parent is not None and (
                top.parent.type in WRAPPERS
                or top.parent.type == "member_expression" and top.parent.child_by_field_name("object").id == top.id
                or top.parent.type == "call_expression" and top.parent.child_by_field_name("function").id == top.id):
            top = top.parent
        p = top.parent
        if p is None:
            return None
        if p.type == "variable_declarator":
            name = p.child_by_field_name("name")
            return text(name, self.src) if name is not None and name.type == "identifier" else None
        if p.type == "export_statement":
            return "default" if any(c.type == "default" for c in p.children) else None
        if p.type == "assignment_expression":
            return self._exported_as(text(p.child_by_field_name("left"), self.src))
        return None

    @staticmethod
    def _exported_as(left: str) -> str | None:
        """`module.exports` → `default`; `exports.x` / `module.exports.x` → `x`; anything else → None."""
        if left == "module.exports":
            return "default"
        if left.startswith("exports.") and left.count(".") == 1 or left.startswith("module.exports.") and left.count(".") == 2:
            return left.split(".")[-1]
        return None

    def region_of(self, call: Node, fn: Node) -> Region | None:
        """fastify `instance.register(function (child) {...}, { prefix: '/v1' })`: the plugin's routes under the prefix."""
        callee = call.child_by_field_name("function")
        args = call.child_by_field_name("arguments")
        if callee is None or args is None or callee.type != "member_expression":
            return None
        if text(callee.child_by_field_name("property"), self.src) != "register":
            return None
        p = ""
        for a in args.children:
            if a.type == "object":
                for key, val in self._keyed_fields(a):
                    if key == "prefix":
                        p = self.path_of(val) or ""
        return Region(text(callee.child_by_field_name("object"), self.src).split(".")[-1], p, same_router=False)

    def _decorator(self, n: Node, controller_prefix: dict[int, list[str]]) -> None:
        """Nest: `@Controller(prefix)` on a class, `@Get(path)` on its methods. A route waits for `compose`, which puts
        it under its package's `setGlobalPrefix`."""
        call = next((c for c in n.named_children if c.type == "call_expression"), None)
        fn = call.child_by_field_name("function") if call is not None else None
        kind = text(fn, self.src) if fn is not None and fn.type == "identifier" else ""
        if kind not in NEST_DECORATORS:
            return
        args = call.child_by_field_name("arguments")
        first = args.named_children[0] if args is not None and args.named_child_count else None
        paths = ["/" + p.strip("/") if p else "" for p in self._nest_paths(first)]
        if kind == "Controller":
            target = n.parent
            if target is not None and target.type == "export_statement":
                target = next((c for c in target.named_children if c.type in ("class_declaration", "class")), target)
            if target is not None:
                controller_prefix[target.id] = paths
            return
        cls = n.parent
        while cls is not None and cls.type not in ("class_declaration", "class"):
            cls = cls.parent
        prefixes = controller_prefix.get(cls.id, [""]) if cls is not None else [""]
        sib = n.next_named_sibling
        while sib is not None and sib.type in ("decorator", "comment"):      # `@Get('x')  // why`
            sib = sib.next_named_sibling
        handler_node = sib.child_by_field_name("name") if sib is not None and sib.type in ("method_definition", "public_field_definition") else None
        hname, hid = self.resolve_handler(handler_node) if handler_node is not None else (None, None)
        method = "ANY" if kind == "All" else kind.upper()
        for prefix in prefixes:
            for p in paths:
                ep = self.add_endpoint(n, method, p or "/", "nest", None, prefix=prefix, handler_name=hname, handler_id=hid)
                if ep is not None:
                    self.out.pending.append(Pending(ep, "ts.nest", (self.fx.file.module_id,)))

    def _nest_paths(self, a: Node | None) -> list[str]:
        """The paths a Nest decorator argument gives: `'cats'`, `['a', 'b']`, `{ path: 'cats' }`, or a constant —
        `RouteKey.Asset`, an enum member, also of another file. [""] when there is none or it cannot be read."""
        if a is None:
            return [""]
        if a.type == "string" or a.type == "template_string" and not has_interpolation(a):
            return [unquote(text(a, self.src))]
        if a.type == "array":
            return [p for c in a.named_children for p in self._nest_paths(c)] or [""]
        if a.type == "object":
            path = next((v for k, v in self._keyed_fields(a) if k == "path"), None)
            return self._nest_paths(path) if path is not None else [""]
        if a.type in ("identifier", "member_expression"):
            name = text(a, self.src)
            found = self.ctx.route_const(name) or self.ctx.segment_const(name) or self.foreign_const(name, segment=True)
            return [found] if found is not None else [""]
        return [""]

    def _global_prefix(self, arg_nodes: list[Node]) -> None:
        """Nest `app.setGlobalPrefix('api', { exclude: [..] })`: every controller route of this package goes under the
        prefix but the excluded ones (`compose`). The list may be another file's (`exclude: excludePaths`)."""
        prefix = self._nest_paths(arg_nodes[0])[0]
        opts = arg_nodes[1] if len(arg_nodes) > 1 and arg_nodes[1].type == "object" else None
        ex = next((v for k, v in self._keyed_fields(opts) if k == "exclude"), None) if opts is not None else None
        ref = None
        if ex is not None and ex.type == "identifier":
            local = self.resolve_local(ex)
            unit = self._function_unit(ex) if local is None else None
            ex, ref = local, (f"{unit[0]}:{unit[1]}" if unit is not None else None)
        excludes = tuple(p for c in ex.named_children for p in self._nest_paths(c) if p) \
            if ex is not None and ex.type == "array" else ()
        if prefix:
            self.out.publish("ts.nest-prefix", self.fx.file.module_id, ("/" + prefix.strip("/"), excludes, ref))

    def _string_array(self, n: Node) -> None:
        """`export const excludePaths = ['/.well-known/immich', ..]`: published for another file's
        `setGlobalPrefix(.., { exclude: excludePaths })`."""
        name, val, decl = n.child_by_field_name("name"), n.child_by_field_name("value"), n.parent
        if name is None or val is None or val.type != "array" or decl is None or decl.parent is None \
                or decl.parent.type != "export_statement":
            return
        items = tuple(unquote(text(c, self.src)) for c in val.named_children if c.type == "string")
        if items and len(items) == val.named_child_count:
            self.out.publish("ts.string-array", f"{self.fx.file.path}:{text(name, self.src)}", items)

    def _call(self, n: Node) -> None:
        """A registration inside a route wrapper is a route as written until `compose` sees the wrapper used."""
        before = len(self.out.endpoints)
        self._read_call(n)
        owner = self.wrapped.get(n.id)
        for ep in self.out.endpoints[before:] if owner is not None else ():
            self.out.pending.append(Pending(ep, "ts.wrapped", (owner,)))

    def _read_call(self, n: Node) -> None:
        fn = n.child_by_field_name("function")
        args = n.child_by_field_name("arguments")
        if fn is not None and fn.type == "await_expression" and fn.named_child_count == 1:
            fn = fn.named_children[0]                # `await api.post<T>(..)`: the grammar puts the `await` in the callee
        if fn is None or args is None:
            return
        callee = self.callee_of(fn)
        name, recv, recv_last = split_callee(callee)
        obj = fn.child_by_field_name("object") if fn.type == "member_expression" else None
        if obj is not None and obj.type in ("call_expression", "new_expression"):
            recv_last = self._chain_router(obj) or recv_last
        arg_nodes = [c for c in args.children if c.is_named]
        if not arg_nodes:
            return
        self._router_arguments(n, fn, arg_nodes)
        if "getHttpServer" in callee or "supertest" in callee or "request(app" in callee:
            return                                                  # supertest-style test clients
        if name == "setGlobalPrefix":
            self._global_prefix(arg_nodes)
            return
        if self.convention_call(n, name, recv_last, callee, arg_nodes):
            return
        if self._mount(n, name, recv_last, arg_nodes):
            return
        if self._chained_route(n, arg_nodes):
            return
        if self._wrapper_call(n, name, recv_last, arg_nodes):
            return
        self._wrapped_route_call(n, name, arg_nodes)            # a candidate only: the call may still be a request
        if self.oazapfts and name in OAZAPFTS and recv_last == "oazapfts":
            self._oazapfts_call(n, arg_nodes)
            return
        if self._config_request(n, name, callee, arg_nodes):
            return
        if recv_last in JQUERY:                                     # browser code: `$.get(url, cb)` is a request, cb is no handler
            p = self.path_of(arg_nodes[0], lenient=True) if name in JQUERY_VERBS else None
            if p is not None:
                self.add_call(n, JQUERY_VERBS[name], p, callee)
            return
        if (name in TS_REGISTRARS or name in TS_ROUTER_VERBS and recv_last in self.router_vars) and len(arg_nodes) >= 2:
            p = self.route_path(arg_nodes[0], recv_last, n)
            if p is not None and (p.startswith("/") or isinstance(p, MountedRoot)) \
                    and (self.is_handler_like(arg_nodes[-1]) or recv_last in self.router_vars) \
                    and (recv_last in self.router_vars or not CLIENT_RECEIVER.search(recv_last)):   # `const api = express.Router()`
                if name == "route":                                  # app.route('/x').get(h) — take the verb from the chain
                    return
                self.add_endpoint(n, TS_ROUTER_VERBS.get(name) or VERB_BY_NAME.get(name, "ANY"), p, "express", arg_nodes[-1],
                                  router=recv_last)
                return
        if name in OUTBOUND or name in TS_VERB_ALIASES:
            verb = name in VERB_BY_NAME or name in TS_VERB_ALIASES
            client = self._client_of(callee) is not None
            if verb and len(arg_nodes) >= 2 and self.is_handler_like(arg_nodes[-1]) and not client:
                return
            if name in GENERIC_OUTBOUND and not CLIENT_RECEIVER.search(recv_last):
                return
            if verb and not (CLIENT_RECEIVER.search(recv_last) or recv_last in ("http", "this") or client):
                return                                                  # cache.get(key), map.delete(k), redis.del(k) ...
            method = OUTBOUND.get(name) or TS_VERB_ALIASES.get(name) or self.method_from_args(arg_nodes)
            if method is None and name in ("fetch", "$fetch", "ofetch") \
                    and not any(re.search(r"\bmethod\s*:", text(a, self.src)) for a in arg_nodes[1:]):
                method = "GET"                                      # fetch(url) / fetch(url, { headers }) is a GET
            lenient = name in ("fetch", "$fetch", "ofetch") or bool(CLIENT_RECEIVER.search(recv_last))
            for a in arg_nodes:
                p = self.path_of(a, lenient=lenient)
                if p is not None:
                    self.add_call(n, method, p, callee)
                    return

    def _config_request(self, n: Node, name: str, callee: str, arg_nodes: list[Node]) -> bool:
        """A request described by an object — `channel.post({ url: "/json/bots" })`, `axios.request({ url, method:
        'POST' })`, openapi-ts' `(options.client ?? client).post({ url: '/api/v1/users/' })`, `$.ajax(url, { type })`:
        a `url` holding a path is the request, whatever the receiver is called. The verb is the method's name, else the
        object's `method` (`type` for jQuery), else GET."""
        verb = VERB_BY_NAME.get(name) or TS_VERB_ALIASES.get(name)
        if verb is None and name not in CONFIG_REQUESTS:
            return False
        objs = [unwrap_arg(a) for a in arg_nodes if unwrap_arg(a).type == "object"]
        fields = {k: v for o in objs[:1] for k, v in self._own_fields(o)}
        url = fields.get("url")
        if url is None and name == "ajax" and arg_nodes[0].type != "object":
            url = arg_nodes[0]                                       # $.ajax(url, settings)
        p = self.path_of(url, lenient=True) if url is not None else None
        if p is None:
            return False
        given = fields.get("method") or fields.get("type")
        given = unquote(text(given, self.src)).upper() if given is not None and given.type == "string" else None
        self.add_call(n, verb or (given if given in HTTP_METHODS else None) or "GET", p, callee)
        return True

    def _own_fields(self, n: Node) -> list[tuple[str, Node]]:
        """(key, value) of an object literal's own pairs — not of the objects inside it."""
        out = []
        for d in n.named_children:
            key, value = d.child_by_field_name("key"), d.child_by_field_name("value")
            if d.type == "pair" and key is not None and value is not None:
                out.append((unquote(text(key, self.src)), value))
        return out

    def _oazapfts_call(self, n: Node, arg_nodes: list[Node]) -> None:
        """oazapfts' generated client: `oazapfts.fetchJson<T>(`/activities/${encodeURIComponent(id)}${QS.query(..)}`,
        oazapfts.json({ ...opts, method: "POST" }))` — the path without its query string, under the client's `baseUrl`
        (`defaults.baseUrl = "/api"`); the verb from the options, GET without one."""
        p = arg_nodes[0]
        if p.type == "template_string":
            raw = "".join(text(c, self.src) if c.type == "string_fragment" else
                          "" if re.search(r"\.query\(", text(c, self.src)) else "{param}"
                          for c in p.named_children)
        elif p.type == "string":
            raw = unquote(text(p, self.src))
        else:
            return
        opts = unwrap_arg(arg_nodes[1]) if len(arg_nodes) > 1 else None
        if opts is not None and opts.type == "call_expression":           # oazapfts.json({..}), .multipart({..})
            inner = opts.child_by_field_name("arguments")
            opts = inner.named_children[0] if inner is not None and inner.named_child_count else None
        method = next((unquote(text(v, self.src)).upper() for k, v in self._own_fields(opts) if k == "method"),
                      "GET") if opts is not None and opts.type == "object" else "GET"
        self.add_call(n, method, self.oazapfts_base + raw, "generated-client")

    # -- a project's own mount wrappers: `app.lazyUse(path, require('./x'))` ---------------------------------------
    def _mount_wrapper(self, fn: Node) -> None:
        """`app.lazyUse = function lazyUse(mountPath, requireFn) { app.use(mountPath, lazyLoad(() => requireFn())) }`:
        a method that mounts what it is given under the path it is given. Published for `compose`, which turns its
        calls in any file into mounts: (position of the path, of the router, whether the method calls the router)."""
        name = self._wrapper_name(fn, declared=False)
        params = self._params(fn) if name else []
        body = fn.child_by_field_name("body")
        if len(params) < 2 or body is None:
            return
        for c in walk(body):
            _, link = member(c.child_by_field_name("function")) if c.type == "call_expression" else (None, None)
            args = c.child_by_field_name("arguments") if link is not None and text(link, self.src) == "use" else None
            kids = args.named_children if args is not None else []
            if len(kids) < 2 or kids[0].type != "identifier" or text(kids[0], self.src) not in params:
                continue
            i = params.index(text(kids[0], self.src))
            for x in (x for k in kids[1:] for x in walk(k) if x.type == "identifier"):
                j = params.index(text(x, self.src)) if text(x, self.src) in params else i
                if j != i:
                    f = x.parent.child_by_field_name("function") if x.parent.type == "call_expression" else None
                    self.out.publish("ts.mount-wrapper", name, (i, j, f is not None and f.id == x.id))
            return

    def _wrapper_name(self, fn: Node, declared: bool) -> str | None:
        """The name a wrapper is called by: a method's, or the property a function is assigned to
        (`helpers.setupApiRoute = function ..`); with `declared`, also `function x(..)` and `const x = (..) => ..`."""
        if fn.type == "method_definition":
            return text(fn.child_by_field_name("name"), self.src)
        if fn.parent is not None and fn.parent.type == "assignment_expression":
            _, prop = member(fn.parent.child_by_field_name("left"))
            return text(prop, self.src) if prop is not None else None
        name = self._fn_name(fn) if declared else None
        return name if name != "default" else None

    # -- a project's own route wrappers: `setupApiRoute(router, 'post', '/x', mws, handler)` ------------------------
    def _route_wrapper(self, fn: Node) -> None:
        """A function that registers routes on the router and under the path it is given — NodeBB's
        `helpers.setupApiRoute = function (...args) { const [router, verb, name] = args; .. router[verb](name, ..) }`,
        `setupPageRoute(router, name, ..)` registering `router.get(name, ..)` and `` router.get(`/api${name}`, ..) ``.
        Its shapes — (position of the router, the verb or the position of the argument naming it, position of the
        path, the path around it) — are published for `compose`, which makes its calls in any file routes, and then
        drops the registrations in its body, which are templates of them (`GET /api{param}`)."""
        name = self._wrapper_name(fn, declared=True)
        params = self._wrapper_params(fn) if name else {}
        body = fn.child_by_field_name("body")
        if len(params) < 2 or body is None:
            return
        shapes = []
        for c in walk(body):
            f = c.child_by_field_name("function") if c.type == "call_expression" else None
            args = c.child_by_field_name("arguments") if f is not None else None
            if args is None or not args.named_child_count:
                continue
            if f.type == "subscript_expression":                     # router[verb](name, ..)
                obj, idx = f.child_by_field_name("object"), f.child_by_field_name("index")
                verb = ("arg", params[text(idx, self.src)]) \
                    if idx is not None and idx.type == "identifier" and text(idx, self.src) in params else None
            else:
                obj, prop = member(f)
                method = TS_CHAIN_VERBS.get(text(prop, self.src)) if prop is not None else None
                verb = ("verb", method) if method else None
            if verb is None or obj is None or obj.type != "identifier" or text(obj, self.src) not in params:
                continue
            path = self._param_template(args.named_children[0], params)
            if path is not None:
                shapes.append((params[text(obj, self.src)], verb, *path))
                self.wrapped[c.id] = name
        for shape in dict.fromkeys(shapes):
            self.out.publish("ts.route-wrapper", name, shape)

    def _wrapper_params(self, fn: Node) -> dict[str, int]:
        """Positions of `fn`'s parameters by name, and of the names a rest parameter is destructured into
        (`(...args) => { const [router, verb, name] = args; .. }`)."""
        params = fn.child_by_field_name("parameters")
        out: dict[str, int] = {}
        rest: tuple[str, int] | None = None
        for i, d in enumerate(params.named_children if params is not None else ()):
            pat = d.child_by_field_name("pattern") or d                     # TS wraps it in a required_parameter
            if pat.type == "rest_pattern":
                ident = next((c for c in pat.named_children if c.type == "identifier"), None)
                rest = (text(ident, self.src), i) if ident is not None else None
                continue
            ident = pat if pat.type == "identifier" else pat.child_by_field_name("left")
            if ident is not None and ident.type == "identifier":
                out[text(ident, self.src)] = i
        body = fn.child_by_field_name("body")
        decls = [d for st in (body.named_children if rest is not None and body is not None else ())
                 if st.type in ("lexical_declaration", "variable_declaration") for d in st.named_children]
        for d in decls:
            name, value = d.child_by_field_name("name"), d.child_by_field_name("value")
            if name is None or name.type != "array_pattern" or value is None or text(value, self.src) != rest[0]:
                continue
            pos = 0
            for el in name.children:
                if el.type == ",":
                    pos += 1
                elif el.type == "identifier":
                    out[text(el, self.src)] = rest[1] + pos
        return out

    def _param_template(self, n: Node, params: dict[str, int]) -> tuple[int, str] | None:
        """`name` → (its position, "{}"); `` `/api${name}` `` → (its position, "/api{}"): a path made of one
        parameter."""
        if n.type == "identifier":
            return (params[text(n, self.src)], "{}") if text(n, self.src) in params else None
        subs = [c for c in n.named_children if c.type == "template_substitution"] if n.type == "template_string" else []
        inner = subs[0].named_children if len(subs) == 1 else []
        if len(inner) != 1 or inner[0].type != "identifier" or text(inner[0], self.src) not in params:
            return None
        before, _, after = text(n, self.src)[1:-1].partition(text(subs[0], self.src))
        return (params[text(inner[0], self.src)], before + "{}" + after) if "${" not in before + after else None

    def _wrapped_route_call(self, n: Node, name: str, arg_nodes: list[Node]) -> None:
        """`setupApiRoute(router, 'post', '/x', mws, handler)`, `helpers.setupPageRoute(app, '/x', .., handler)`: a
        route if some file defines `name` as a route wrapper (`_route_wrapper`) — a candidate here, made a route in
        `compose`, with the handler in the last argument. A path with a part this file cannot read
        (`` `/${name}/x` ``, NodeBB's remountable prefixes) makes none: the linker compares literal segments, so
        `/{param}/x` would link nothing."""
        if len(arg_nodes) < 3 or name in TS_REGISTRARS or name in TS_MOUNTS or name in OUTBOUND \
                or name in TS_VERB_ALIASES:
            return
        args = []
        for a in map(unwrap_arg, arg_nodes):
            lit = unquote(text(a, self.src)).strip() if a.type == "string" else None
            p = self.path_of(a)                                 # `/${name}/x`: a prefix only known at run time — none
            p = p if p is not None and p.startswith("/") and "{param}" not in p \
                else "/" if lit in ("/", "") and lit is not None else None
            verb = lit.upper() if lit and lit.upper() in HTTP_METHODS else TS_VERB_ALIASES.get(lit or "")
            args.append((p, verb))
        routers = {i: text(a, self.src) for i, a in enumerate(arg_nodes)
                   if a.type == "identifier" and args[i] == (None, None)}
        if not routers or not any(p for p, _ in args):
            return
        hname, hid = self.resolve_handler(arg_nodes[-1])
        base = self.endpoint_info(n, "ANY", "/", "express", hname, hid)
        self.route_calls.append((name, tuple(args), {i: (self.router_key(r, n), self.prefix_for(r, n) or "")
                                                     for i, r in routers.items()}, base))

    def _wrapper_call(self, n: Node, name: str, recv_last: str, arg_nodes: list[Node]) -> bool:
        """`backendApp.lazyUse('/ghost/api', require('../api'))` on a router, with a method no framework has: a mount if
        some file defines that method as one (`_mount_wrapper`) — a candidate here, settled in `compose`."""
        if recv_last not in self.router_vars or name in TS_REGISTRARS or name in TS_ROUTER_VERBS or name in TS_MOUNTS \
                or len(arg_nodes) < 2:
            return False
        found = False
        for i, a in enumerate(arg_nodes):
            p = self.path_of(a)
            if p is None or not p.startswith("/"):
                continue
            prefix = (self.prefix_for(recv_last, n) or "").rstrip("/") + p
            for j, b in enumerate(arg_nodes):
                value, called = self._child_ids(b) if j != i else (None, None)
                if value is not None or called is not None:
                    self.maybe_mounts.append((name, i, j, value, called, self.router_key(recv_last, n), prefix))
                    found = True
        return found

    # -- routers other files name: imports, exports, module variables, router parameters, returned routers ---------
    def read_imports(self) -> dict[str, tuple[str, str | None]]:
        """`import r from './r'` → r: ('./r', 'default'); `import { a as b }` → b: (.., 'a'); `import * as m` → m: (..,
        None); `const r = require('./r')` → r: ('./r', 'default') (what `module.exports` holds); `require('./r').x` and
        `const { x } = require('./r')` → x: ('./r', 'x')."""
        out: dict[str, tuple[str, str | None]] = {}
        for n in walk(self.fx.tree.root_node):
            if n.type == "import_statement":
                source = n.child_by_field_name("source")
                clause = next((c for c in n.named_children if c.type == "import_clause"), None)
                if source is None or clause is None:
                    continue
                spec = unquote(text(source, self.src))
                for c in clause.named_children:
                    if c.type == "identifier":
                        out[text(c, self.src)] = (spec, "default")
                    elif c.type == "namespace_import":
                        ident = next((x for x in c.named_children if x.type == "identifier"), None)
                        if ident is not None:
                            out[text(ident, self.src)] = (spec, None)
                    elif c.type == "named_imports":
                        for s in c.named_children:
                            name, alias = s.child_by_field_name("name"), s.child_by_field_name("alias")
                            if s.type == "import_specifier" and name is not None:
                                out[text(alias if alias is not None else name, self.src)] = (spec, text(name, self.src))
            elif n.type == "variable_declarator":
                spec, prop = self._required(n.child_by_field_name("value"))
                name = n.child_by_field_name("name")
                if spec is None or name is None:
                    continue
                if name.type == "identifier":
                    out[text(name, self.src)] = (spec, prop or "default")
                elif name.type == "object_pattern" and prop is None:
                    for p in name.named_children:
                        if p.type == "shorthand_property_identifier_pattern":
                            out[text(p, self.src)] = (spec, text(p, self.src))
                        elif p.type == "pair_pattern":
                            key, value = p.child_by_field_name("key"), p.child_by_field_name("value")
                            if key is not None and value is not None and value.type == "identifier":
                                out[text(value, self.src)] = (spec, unquote(text(key, self.src)))
        return out

    def _required(self, n: Node | None) -> tuple[str | None, str | None]:
        """`require('./x')` → ('./x', None); `require('./x').y` → ('./x', 'y'); anything else → (None, None)."""
        prop = None
        if n is not None and n.type == "member_expression":
            n, p = member(n)
            prop = text(p, self.src) if p is not None else None
        if n is None or n.type != "call_expression":
            return None, None
        fn, args = n.child_by_field_name("function"), n.child_by_field_name("arguments")
        if fn is None or args is None or text(fn, self.src) != "require" or args.named_child_count != 1 \
                or args.named_children[0].type != "string":
            return None, None
        return unquote(text(args.named_children[0], self.src)), prop

    def _function_unit(self, f: Node | None) -> tuple[str, str] | None:
        """What `f` names in a file of the repo, as (that file, the name there): an import (`routes`, `m.routes`), the
        module of `require('./x')`, or a function of this file."""
        if f is None:
            return None
        spec, prop = self._required(f)
        if spec is not None:
            target = self.resolve_import(spec)
            return (target, prop or "default") if target is not None else None
        if f.type == "identifier":
            name = text(f, self.src)
            spec, orig = self.imports.get(name) or (None, None)
            if spec is not None:
                target = self.resolve_import(spec) if orig is not None else None
                return (target, orig) if target is not None else None
            if any(s.kind == "function" for s in self.symbols_by_name.get(name, ())):
                return self.fx.file.path, name
            return None
        obj, prop = member(f)
        if obj is None or prop is None or obj.type != "identifier":
            return None
        spec, _ = self.imports.get(text(obj, self.src)) or (None, None)
        target = self.resolve_import(spec) if spec is not None else None
        return (target, text(prop, self.src)) if target is not None else None

    def _child_ids(self, a: Node) -> tuple[str | None, str | None]:
        """The router an argument is, by the global id another file knows it by: (the argument as it is —
        `routes`, `require('./x')`, `routes()` —, what it returns once called — the function `routes`, the module's
        export)."""
        a = unwrap_arg(a)
        if a.type == "call_expression" and self._required(a)[0] is None:
            unit = self._function_unit(a.child_by_field_name("function"))
            return (f"ret:{unit[0]}:{unit[1]}", None) if unit is not None else (None, None)
        unit = self._function_unit(a)
        return (f"var:{unit[0]}:{unit[1]}", f"ret:{unit[0]}:{unit[1]}") if unit is not None else (None, None)

    def _router_arguments(self, n: Node, fn: Node, arg_nodes: list[Node]) -> None:
        """`require('./legacy')(app)`, `setupRoutes(router)`: a router handed to a function of this repo — the routes
        it registers on that parameter go where this router goes."""
        unit = self._function_unit(fn)
        if unit is None:
            return
        for i, a in enumerate(arg_nodes):
            if a.type == "identifier":
                self.router_args.append((f"param:{unit[0]}:{unit[1]}:{i}", text(a, self.src), n, ""))

    def _params(self, fn: Node) -> list[str]:
        """Names of `fn`'s parameters in order ("" for a destructured one)."""
        params = fn.child_by_field_name("parameters")
        if params is None:
            one = fn.child_by_field_name("parameter")                 # x => ...
            return [text(one, self.src)] if one is not None and one.type == "identifier" else []
        out = []
        for d in params.named_children:
            ident = d if d.type == "identifier" else d.child_by_field_name("pattern") or d.child_by_field_name("left")
            out.append(text(ident, self.src) if ident is not None and ident.type == "identifier" else "")
        return out

    def _fn_name(self, fn: Node) -> str | None:
        """The name other files call a function by: `default` for the module's default export (`module.exports = () =>
        ..`, `export default function ..`), `x` for `exports.x = ..`, else its declared or bound name."""
        p = fn.parent
        if p is not None and p.type == "export_statement" and any(c.type == "default" for c in p.children):
            return "default"
        if p is not None and p.type == "assignment_expression":
            return self._exported_as(text(p.child_by_field_name("left"), self.src))
        if p is not None and p.type == "variable_declarator":
            name = p.child_by_field_name("name")
            return text(name, self.src) if name is not None and name.type == "identifier" else None
        name = fn.child_by_field_name("name")
        if fn.type in ("function_declaration", "generator_function_declaration") and name is not None:
            return text(name, self.src)
        return None

    def global_of(self, key: tuple[int, str]) -> str | None:
        scope, name = key
        path = self.fx.file.path
        if scope == 0:
            if name == "default" or re.fullmatch(r"[A-Za-z_$][\w$]*", name) and self.module_binds(name):
                return f"var:{path}:{name}"
            spec, orig = self.imports.get(name) or (None, None)
            target = self.resolve_import(spec) if spec is not None and orig is not None else None
            return f"var:{target}:{orig}" if target is not None else None
        fn = self.function_of(scope)
        fname = self._fn_name(fn) if fn is not None else None
        if fname is None:
            return None
        params = self._params(fn)
        if name in params:
            return f"param:{path}:{fname}:{params.index(name)}"
        return f"ret:{path}:{fname}" if self.returns_name(fn, name) else None

    def _exports(self) -> tuple[list[tuple[str, str]], list[tuple[str, str, str]]]:
        """What this file exports under another name, as (local name, exported name) — `export default router`,
        `module.exports = router`, `module.exports = { a: b }`, `exports.x = y`, `export { a as b }` —, and what it
        re-exports from another file, as (spec, name there, exported name) — `module.exports = require('./app')`,
        `export { a } from './x'`."""
        aliases: list[tuple[str, str]] = []
        reexports: list[tuple[str, str, str]] = []
        for n in self.fx.tree.root_node.named_children:
            if n.type == "export_statement":
                source = n.child_by_field_name("source")
                value = n.child_by_field_name("value") or n.child_by_field_name("declaration")
                if value is not None and any(c.type == "default" for c in n.children):
                    local = self._declared_name(value)
                    if local is not None:
                        aliases.append((local, "default"))
                for s in (s for c in n.named_children if c.type == "export_clause" for s in c.named_children):
                    name, alias = s.child_by_field_name("name"), s.child_by_field_name("alias")
                    if s.type != "export_specifier" or name is None:
                        continue
                    orig = text(name, self.src)
                    exported = text(alias, self.src) if alias is not None else orig
                    if source is not None:
                        reexports.append((unquote(text(source, self.src)), orig, exported))
                    elif exported != orig:
                        aliases.append((orig, exported))
            elif n.type == "expression_statement" and n.named_child_count == 1 \
                    and n.named_children[0].type == "assignment_expression":
                a = n.named_children[0]
                exported = self._exported_as(text(a.child_by_field_name("left"), self.src))
                right = a.child_by_field_name("right")
                if exported is None or right is None:
                    continue
                spec, prop = self._required(right)
                if spec is not None:
                    reexports.append((spec, prop or "default", exported))
                elif right.type == "object" and exported == "default":
                    for pair in (p for p in right.named_children if p.type == "pair"):
                        key, value = pair.child_by_field_name("key"), pair.child_by_field_name("value")
                        if key is not None and value is not None and value.type == "identifier":
                            aliases.append((text(value, self.src), unquote(text(key, self.src))))
                else:
                    local = self._declared_name(right)
                    if local is not None and local != exported:
                        aliases.append((local, exported))
        return aliases, reexports

    def _returned_module_routers(self) -> list[tuple[str, str]]:
        """`const router = Router(); .. module.exports = function () { ..; return router; }`: what the function returns
        is the module's router — (its id, the function's `ret:`)."""
        out = []
        for r in (r for r in walk(self.fx.tree.root_node) if r.type == "return_statement") if self.router_vars else ():
            vals = [c for c in r.named_children if c.type != "comment"]
            name = text(vals[0], self.src) if len(vals) == 1 and vals[0].type == "identifier" else None
            fn = r.parent
            while fn is not None and fn.type not in FUNCTIONS:
                fn = fn.parent
            fname = self._fn_name(fn) if fn is not None and name in self.router_vars else None
            if fname is not None and self.scopes.binding_scope(name, r) == 0 and self.module_binds(name):
                out.append((f"var:{self.fx.file.path}:{name}", f"ret:{self.fx.file.path}:{fname}"))
        return out

    def _declared_name(self, n: Node) -> str | None:
        """`router` (a name) or `function apiRoutes() {..}` (a named function) — what an export statement exports."""
        if n.type == "identifier":
            return text(n, self.src)
        name = n.child_by_field_name("name") if n.type in ("function_declaration", "function_expression", "function",
                                                            "class_declaration", "class") else None
        return text(name, self.src) if name is not None else None

    def finish(self) -> None:
        """The file's mounts (`BaseScanner.finish`); then, for `compose`, the candidate wrapper mounts with where their
        receiver leads, and the exports: an exported router (or a function that returns or takes one) is the same as
        the export, an edge with no prefix from the local name to the exported one."""
        super().finish()
        is_app = lambda key: key in self.app_vars                                       # noqa: E731
        for name, i, j, value, called, parent, prefix in self.maybe_mounts:
            for target, pp in self.mounts.targets(parent, self._global, is_app):
                self.out.publish("ts.mount.maybe", name, (i, j, value, called, target, pp.rstrip("/") + prefix))
        for name, args, routers, base in self.route_calls:
            where = {i: (group, self.mounts.targets(key, self._global, is_app)) for i, (key, group) in routers.items()}
            self.out.publish("ts.route.maybe", name, (args, where, base))
        for child, parent in self._returned_module_routers():
            self.out.publish(f"{self.mount_rule}.edge", child, (parent, ""))
        path = self.fx.file.path
        aliases, reexports = self._exports()
        pairs = [(path, local, exported) for local, exported in aliases]
        pairs += [(target, orig, exported) for spec, orig, exported in reexports
                  if (target := self.resolve_import(spec)) is not None]
        for unit, local, exported in pairs:
            for kind in ("var", "ret"):
                self.out.publish(f"{self.mount_rule}.edge", f"{kind}:{unit}:{local}", (f"{kind}:{path}:{exported}", ""))
            for i in range(3):
                self.out.publish(f"{self.mount_rule}.edge", f"param:{unit}:{local}:{i}",
                                 (f"param:{path}:{exported}:{i}", ""))
            if unit == path and (0, local) in self.app_vars:
                self.out.publish(f"{self.mount_rule}.app", f"var:{path}:{exported}", True)

    @classmethod
    def compose(cls, out: HttpResult, repo: RepoInfo, view=None) -> None:
        """The mounts a project's own wrappers make: each candidate call (`_wrapper_call`) whose method some file
        defines as a wrapper with the same shape becomes an edge. Then the mount graph (`BaseScanner.compose`)."""
        routes, used = out.facts.get("ts.route-wrapper", {}), set()
        for name, calls in out.facts.get("ts.route.maybe", {}).items():
            shapes = list(dict.fromkeys(routes.get(name, ())))
            for args, where, base in calls if shapes else ():
                for r, (kind, v), pos, tmpl in shapes:
                    method = v if kind == "verb" else args[v][1] if v < len(args) else None
                    if r not in where or pos >= len(args) or args[pos][0] is None or method is None:
                        continue
                    group, targets = where[r]
                    raws = [tmpl.replace("{}", args[pos][0])]
                    while (m := OPTIONAL_TAIL.search(raws[-1])) is not None:    # /:code? → also without it
                        raws.append(raws[-1][:m.start()] or "/")
                    for raw, target, prefix in ((raw, t, p) for raw in raws for t, p in targets):
                        ep = _wrapped(repo, base, method, group.rstrip("/") + raw if group else raw, raw)
                        root = isinstance(ep.raw_pattern, MountedRoot)
                        if root and not prefix and target == TOP:
                            continue                        # a sub-router's root nothing mounts
                        copy = rebased(repo, ep, prefix) if prefix or root and target == APP else ep
                        out.endpoints.append(copy)
                        used.add(name)
                        if target not in (TOP, APP):
                            out.pending.append(Pending(copy, cls.mount_rule, (target,)))
        replace_endpoints(out, {id(p.item): [] for p in out.pending if p.rule == "ts.wrapped" and p.key[0] in used})
        wrappers = out.facts.get("ts.mount-wrapper", {})
        for name, calls in out.facts.get("ts.mount.maybe", {}).items():
            for wi, wj, wcalled in set(wrappers.get(name, ())):
                for i, j, value, called, target, prefix in calls:
                    child = (called if wcalled else value) if (i, j) == (wi, wj) else None
                    if child is not None:
                        out.publish(f"{cls.mount_rule}.edge", child, (target, prefix))
        super().compose(out, repo, view)
        prefixes, arrays = out.facts.get("ts.nest-prefix", {}), out.facts.get("ts.string-array", {})
        plan = {}
        for p in out.pending:
            found = set(prefixes.get(p.key[0], ())) if p.rule == "ts.nest" else set()
            if len({prefix for prefix, _, _ in found}) != 1:
                continue                                    # no global prefix in the package, or two that disagree
            excludes = [e for _, ex, ref in found for e in ex + tuple(x for t in arrays.get(ref, ()) for x in t)]
            if not _excluded(p.item.path, excludes):
                plan[id(p.item)] = [rebased(repo, p.item, next(iter(found))[0])]
        replace_endpoints(out, plan)


def _wrapped(repo: RepoInfo, base: HttpEndpointInfo, method: str, path: str, raw: str) -> HttpEndpointInfo:
    """The route a wrapper call makes, from the endpoint recorded at the call (`base`: evidence, handler)."""
    path = normalize_path(path)
    pattern = MountedRoot("/") if path == "/" and raw in ("/", "") else raw
    return replace(base, method=method, path=path, raw_pattern=pattern,
                   id=ids.http_endpoint(repo.tenant, repo.name, method, path_key(path)))


def _excluded(path: str, patterns: list[str]) -> bool:
    """A Nest route the global prefix leaves out: `exclude: ['health', 'cats/(.*)', 'docs/{*splat}']`."""
    key = path_key(path)
    for e in patterns:
        e = "/" + e.strip().strip("/")
        wild = re.search(r"/?(\(\.\*\)|\*|\{\*\w*\})", e)
        base = path_key(normalize_path(e[:wild.start()] or "/")) if wild else None
        if base is not None and (key == base or key.startswith(base.rstrip("/") + "/")) \
                or base is None and key == path_key(normalize_path(e)):
            return True
    return False
