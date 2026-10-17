"""TypeScript / JavaScript: express / koa / fastify / Hono (`app.get('/x', handler)`, also chained on the constructor)
+ NestJS decorators (under the package's `setGlobalPrefix`); axios / fetch / got / ky outbound. Routers cross files
through ESM imports and CommonJS `require` / `module.exports` (`global_of`), and through a project's own mount wrappers
(Ghost's `app.lazyUse`)."""

from __future__ import annotations

import re

from tree_sitter import Node

from ...core.http_base import (BaseScanner, CLIENT_RECEIVER, GENERIC_OUTBOUND, OUTBOUND, HttpResult, Pending, Region,
                               rebased, replace_endpoints, split_callee, text, unwrap_arg, walk)
from ...core.http_nodes import has_interpolation, member
from ...core.model import RepoInfo
from ...core.paths import VERB_BY_NAME, normalize_path, path_key, unquote

TS_REGISTRARS = {"get", "post", "put", "patch", "delete", "head", "options", "all", "route"}
TS_CHAIN_VERBS = {v: VERB_BY_NAME[v] for v in ("get", "post", "put", "patch", "delete", "head", "options")} | {"all": "ANY"}
TS_VERB_ALIASES = {"del": "DELETE"}                                       # superagent, NodeBB's api module
TS_MOUNTS = {"use", "route"}
CHAIN_LINKS = TS_REGISTRARS | TS_MOUNTS | {"mount", "basePath", "on", "notFound", "onError"}   # return the router
ROUTER_CTOR = re.compile(r"\b(express|Router|Fastify|fastify|Koa|Hono|Elysia)\s*(<[^()]*>)?\s*\(|\.(Router|router)\(\)")
WRAPPERS = {"parenthesized_expression", "await_expression", "as_expression", "satisfies_expression",
            "non_null_expression"}
FUNCTIONS = {"function_declaration", "function_expression", "function", "arrow_function", "method_definition",
             "generator_function_declaration"}
NEST_DECORATORS = {"Controller", "Get", "Post", "Put", "Patch", "Delete", "Head", "Options", "All"}
JQUERY = {"$", "jQuery"}
JQUERY_VERBS = {"get": "GET", "post": "POST", "getJSON": "GET"}             # $.get(url, data?, success?)


class TsScanner(BaseScanner):
    """express / koa / fastify / Hono (`app.get('/x', handler)`) + NestJS decorators."""
    mount_rule = "ts.mount"

    def run(self) -> None:
        controller_prefix: dict[int, list[str]] = {}
        self.maybe_mounts: list[tuple] = []        # calls of a method that may be a mount wrapper (`_wrapper_call`)
        wraps = b".use(" in self.src
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
            if wraps and n.type in FUNCTIONS:
                self._mount_wrapper(n)

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
            self.group_prefix[nm] = ((self.prefix_for(src.group(1), n) or "") if src else "").rstrip("/") + base.group(1)
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
        p = self.path_of(arg_nodes[0])
        has_path = p is not None and p.startswith("/")
        if name == "route" and (len(arg_nodes) != 2 or not has_path):
            return False                                           # express app.route('/x').get(h)
        if not has_path and name != "use":
            return False
        mounted = False
        for c in (arg_nodes[1:] if has_path else arg_nodes):
            c = unwrap_arg(c)
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
        fn = n.child_by_field_name("function")
        args = n.child_by_field_name("arguments")
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
        if recv_last in JQUERY:                                     # browser code: `$.get(url, cb)` is a request, cb is no handler
            p = self.path_of(arg_nodes[0], lenient=True) if name in JQUERY_VERBS else None
            if p is not None:
                self.add_call(n, JQUERY_VERBS[name], p, callee)
            return
        if name in TS_REGISTRARS and len(arg_nodes) >= 2:
            p = self.route_path(arg_nodes[0], recv_last, n)
            if p is not None and p.startswith("/") and (self.is_handler_like(arg_nodes[-1]) or recv_last in self.router_vars) \
                    and (recv_last in self.router_vars or not CLIENT_RECEIVER.search(recv_last)):   # `const api = express.Router()`
                if name == "route":                                  # app.route('/x').get(h) — take the verb from the chain
                    return
                self.add_endpoint(n, VERB_BY_NAME.get(name, "ANY"), p, "express", arg_nodes[-1], router=recv_last)
                return
        if name in OUTBOUND or name in TS_VERB_ALIASES:
            verb = name in VERB_BY_NAME or name in TS_VERB_ALIASES
            if verb and len(arg_nodes) >= 2 and self.is_handler_like(arg_nodes[-1]):
                return
            if name in GENERIC_OUTBOUND and not CLIENT_RECEIVER.search(recv_last):
                return
            if verb and not (CLIENT_RECEIVER.search(recv_last) or recv_last in ("http", "this")):
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

    # -- a project's own mount wrappers: `app.lazyUse(path, require('./x'))` ---------------------------------------
    def _mount_wrapper(self, fn: Node) -> None:
        """`app.lazyUse = function lazyUse(mountPath, requireFn) { app.use(mountPath, lazyLoad(() => requireFn())) }`:
        a method that mounts what it is given under the path it is given. Published for `compose`, which turns its
        calls in any file into mounts: (position of the path, of the router, whether the method calls the router)."""
        name = None
        if fn.type == "method_definition":
            name = text(fn.child_by_field_name("name"), self.src)
        elif fn.parent is not None and fn.parent.type == "assignment_expression":
            _, prop = member(fn.parent.child_by_field_name("left"))
            name = text(prop, self.src) if prop is not None else None
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

    def _wrapper_call(self, n: Node, name: str, recv_last: str, arg_nodes: list[Node]) -> bool:
        """`backendApp.lazyUse('/ghost/api', require('../api'))` on a router, with a method no framework has: a mount if
        some file defines that method as one (`_mount_wrapper`) — a candidate here, settled in `compose`."""
        if recv_last not in self.router_vars or name in TS_REGISTRARS or name in TS_MOUNTS or len(arg_nodes) < 2:
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
