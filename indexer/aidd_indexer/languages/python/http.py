"""Python: FastAPI (APIRouter prefix) / Flask (Blueprint url_prefix) / Starlette decorators, flask-restx resources;
requests / httpx / aiohttp outbound."""

from __future__ import annotations

import re

from tree_sitter import Node

from ...core.http_base import BaseScanner, CLIENT_RECEIVER, OUTBOUND, split_callee, text, walk
from .package_facts import PREFIX_KEYWORDS, PyFacts
from ...core.paths import HTTP_METHODS, VERB_BY_NAME, unquote
from .client_wrappers import PyClientWrappers, compose_wrapped_calls

PY_REGISTRARS = {"get", "post", "put", "patch", "delete", "head", "options", "route", "api_route", "websocket"}
APP_CLASSES = {"FastAPI", "Flask", "Starlette", "Sanic", "Quart"}
ROUTER_CLASSES = APP_CLASSES | {"APIRouter", "Blueprint", "Router"}
RESTX = ("flask_restx", "flask_restplus", "flask_restful")                             # Namespace, Api, Resource
AIOHTTP = {"add_get": "GET", "add_post": "POST", "add_put": "PUT", "add_patch": "PATCH", "add_delete": "DELETE",
           "add_head": "HEAD", "add_route": None, "add_view": "ANY"}                # app.router.add_*(path, handler)


class PyScanner(PyClientWrappers, BaseScanner):
    """FastAPI / Flask / Starlette decorators; requests / httpx / aiohttp outbound."""
    mount_scope = "py"

    @classmethod
    def compose(cls, out, repo, view=None) -> None:
        super().compose(out, repo, view)
        compose_wrapped_calls(out)

    def run(self) -> None:
        self.test_clients: set[str] = set()
        for n in walk(self.fx.tree.root_node):
            if n.type == "assignment":
                self._maybe_router(n)
                self._maybe_test_client(n.child_by_field_name("left"), n.child_by_field_name("right"))
            elif n.type == "as_pattern":                            # with TestClient(app) as client:
                named = [c for c in n.children if c.is_named]
                self._maybe_test_client(named[-1] if len(named) > 1 else None, named[0] if named else None)
        for n in walk(self.fx.tree.root_node):
            if n.type == "decorated_definition":
                self._decorated(n)
            elif n.type == "class_definition":
                self.publish_bases(n)
            elif n.type == "call":
                if n.parent is not None and n.parent.type == "decorator":
                    continue
                self._call(n)

    def _maybe_router(self, n: Node) -> None:
        left, right = n.child_by_field_name("left"), n.child_by_field_name("right")
        if left is None or right is None or left.type != "identifier" or right.type != "call":
            return
        fn = right.child_by_field_name("function")
        fname = text(fn, self.src).split(".")[-1] if fn is not None else ""
        if fname in ("Namespace", "Api") and self._restx(fn):
            self._restx_router(text(left, self.src), fname, right, n)
            return
        init = None
        if fname not in ROUTER_CLASSES and fname[:1].isupper():
            found = self._router_class(fn)
            if found is not None:
                fname, init = found
        if fname in ROUTER_CLASSES:
            name = text(left, self.src)
            self.router_vars.add(name)
            if fname in APP_CLASSES:                                                    # the application itself
                self.mark_app(name, n)
            args = right.child_by_field_name("arguments")
            kids = args.children if args is not None else ()
            kw = {text(a.child_by_field_name("name"), self.src): a.child_by_field_name("value")
                  for a in kids if a.type == "keyword_argument"}
            pos = [a for a in kids if a.is_named and a.type not in ("keyword_argument", "comment")]
            if init is None or init[0] == "none":
                v = None if init else next((kw[k] for k in PREFIX_KEYWORDS if k in kw), None)
                prefix = unquote(text(v, self.src)) if v is not None and v.type == "string" else ""
            elif init[0] == "lit":
                prefix = init[1]
            else:                                   # ("param", name, position, default): what the call passes for it
                _, pname, at, default = init
                v = kw.get(pname) or (pos[at] if at is not None and at < len(pos) else None)
                prefix = (unquote(text(v, self.src)) if v.type == "string" else "") if v is not None else default or ""
            self.group_prefix[self.group_key(name, n)] = prefix

    def _router_class(self, fn: Node) -> tuple[str, tuple | None] | None:
        """`UserAPIRouter(prefix="/recipes")`: a class of the repo whose bases reach the framework's router —
        (that class, what the first `__init__` up the bases makes of the prefix: `package_facts._init_prefix`). The class
        is this directory's or the import's (`from .routers import UserAPIRouter`, `routers.UserAPIRouter`); a base of
        it, its own directory's, else the one class of that name in the repo."""
        head, _, cname = text(fn, self.src).rpartition(".")
        spec, orig = self.imports.get(head or cname) or (None, None)
        view = self.ctx.view
        if head or spec is not None:                                    # `routers.UserAPIRouter`, or imported by name
            target = (self._module(spec, orig) if head else self.resolve_import(spec) if orig is not None else None) \
                if spec is not None else None
            cname = cname if head else orig
            ctx = view.constants(target) if target is not None and view is not None else None
        else:
            ctx = self.ctx
        init, seen = None, set()
        while ctx is not None and cname not in seen and len(seen) < 6:
            seen.add(cname)
            classes = PyFacts.read(ctx).classes
            info = classes.get(cname)
            if info is None:
                return None
            bases, own = info
            init = init or own
            fw = next((b for b in bases if b in ROUTER_CLASSES), None)
            if fw is not None:
                return fw, init
            for b in bases:
                there = ctx if b in classes else None
                if there is None and view is not None:
                    named = [c for c in view.defining(PyFacts, "classes", b) if PyFacts.read(c).classes.get(b) is not None]
                    there = named[0] if len(named) == 1 else None
                if there is not None:
                    ctx, cname = there, b
                    break
            else:
                return None
        return None

    def _restx(self, fn: Node) -> bool:
        """`Namespace` / `Api` of flask-restx (or flask-restful), not any class of that name."""
        name = text(fn, self.src)
        head = name.split(".")[0]
        spec = (self.imports.get(head) or ("",))[0]
        return spec in RESTX or name.startswith(tuple(m + "." for m in RESTX))

    def _restx_router(self, name: str, kind: str, call: Node, at: Node) -> None:
        """`ns = Namespace("challenges", path="/x")`: a router of resources — its `path` applies, the default
        `/<name>` only by `add_namespace`, which usually gives its own. `Api(bp, prefix="/x")`: a router on the
        blueprint (or app) it is built with, so it takes the blueprint's `url_prefix`."""
        self.router_vars.add(name)
        args = call.child_by_field_name("arguments")
        pos = [a for a in args.children if a.is_named and a.type != "keyword_argument"] if args is not None else []
        kw = {text(a.child_by_field_name("name"), self.src): a.child_by_field_name("value")
              for a in (args.children if args is not None else ()) if a.type == "keyword_argument"}
        own = kw.get("path" if kind == "Namespace" else "prefix")
        self.group_prefix[self.group_key(name, at)] = (self.path_of(own) or "") if own is not None else ""
        if kind == "Api" and pos and pos[0].type == "identifier" and text(pos[0], self.src) in self.router_vars:
            self.mount(name, at, text(pos[0], self.src), at, "")

    def _resource(self, cls: Node, d: Node, p: str, recv: str) -> None:
        """`@ns.route("/<id>")` on a flask-restx `Resource`: a route per HTTP method the class defines."""
        cname = text(cls.child_by_field_name("name"), self.src)
        body = cls.child_by_field_name("body")
        for m in body.named_children if body is not None else ():
            f = m.child_by_field_name("definition") if m.type == "decorated_definition" else m
            if f is None or f.type != "function_definition":
                continue
            mname = text(f.child_by_field_name("name"), self.src)
            if mname.upper() not in HTTP_METHODS:
                continue
            handler = f"{cname}.{mname}"
            hid = next((s.id for s in self.symbols_by_name.get(mname, []) if s.qualified_name.endswith(handler)), None)
            self.add_endpoint(d, mname.upper(), p, "flask-restx", None, handler_name=handler, handler_id=hid,
                              router=recv)

    def _maybe_test_client(self, target: Node | None, value: Node | None) -> None:
        """`TestClient(app)` / `app.test_client()` / Django's `Client()` (`from django.test import Client`, in
        development views): requests through it exercise this app, they are not outbound."""
        if target is None or value is None or value.type != "call":
            return
        fn = value.child_by_field_name("function")
        name = text(fn, self.src).split(".")[-1] if fn is not None else ""
        django = name == "Client" and ((self.imports.get(text(fn, self.src)) or ("",))[0].startswith("django.test")
                                       or text(fn, self.src).startswith("django.test."))
        if name in ("TestClient", "test_client") or django:
            self.test_clients.add(text(target, self.src).split(".")[-1])

    def _decorated(self, n: Node) -> None:
        func = next((c for c in n.children if c.type in ("function_definition", "class_definition")), None)
        fname_node = func.child_by_field_name("name") if func is not None else None
        hname = text(fname_node, self.src) if fname_node is not None else None
        for d in n.children:
            call = next((c for c in d.children if c.type == "call"), None) if d.type == "decorator" else None
            if call is not None:
                self._registration(call, d, hname, func)

    def _registration(self, call: Node, d: Node, hname: str | None, func: Node | None = None) -> bool:
        """`@router.get("/x")` on `hname` (`d`: the decorator) — or applied by hand, `router.post("/register")(fn)`.
        True when `call` is a route registrar."""
        hid = next((s.id for s in self.symbols_by_name.get(hname or "", []) if s.kind in ("function", "method")), None)
        fn = call.child_by_field_name("function")
        args = call.child_by_field_name("arguments")
        if fn is None or args is None or fn.type != "attribute":
            return False
        recv = text(fn.child_by_field_name("object"), self.src).split(".")[-1]
        verb = text(fn.child_by_field_name("attribute"), self.src)
        if verb not in PY_REGISTRARS:
            return False
        arg_nodes = [c for c in args.children if c.is_named]
        if not arg_nodes:
            return False
        p = self.route_path(arg_nodes[0], recv, d) if arg_nodes[0].type == "string" else None
        if p is None or not p.startswith("/"):
            return False
        if func is not None and func.type == "class_definition" and verb == "route":
            self._resource(func, d, p, recv)
            return True
        methods = [VERB_BY_NAME[verb]] if verb in VERB_BY_NAME else ["ANY"]
        if verb in ("route", "api_route"):
            for a in arg_nodes:
                if a.type == "keyword_argument" and text(a.child_by_field_name("name"), self.src) == "methods":
                    found = re.findall(r"[\"']([A-Za-z]+)[\"']", text(a.child_by_field_name("value"), self.src))
                    methods = [m.upper() for m in found if m.upper() in HTTP_METHODS] or ["ANY"]
            if verb == "route" and methods == ["ANY"]:
                methods = ["GET"]                     # Flask default
        if verb == "websocket":
            return True
        framework = "flask" if verb == "route" or recv in ("bp", "blueprint") else "fastapi"
        for m in methods:
            self.add_endpoint(d, m, p, framework, None, handler_name=hname, handler_id=hid, router=recv)
        return True

    def _aiohttp(self, n: Node, fn: Node, args: Node) -> bool:
        """aiohttp: `app.router.add_get('/x', h)`, `router.add_route('*', '/x', h)`, and the bound method
        `add_route = app.router.add_route` called afterwards. The receiver is an application's router, so its
        root is a route; True = recorded."""
        if fn.type == "identifier" and b"router.add_" not in self.src:
            return False                                            # no `add_route = app.router.add_route` here
        target = self.resolve_local(fn) if fn.type == "identifier" else fn
        if target is None or target.type != "attribute":
            return False
        attr, obj = target.child_by_field_name("attribute"), target.child_by_field_name("object")
        if attr is None or obj is None or text(attr, self.src) not in AIOHTTP:
            return False
        recv = self.callee_of(obj)
        if not recv.split(".")[-1].endswith("router"):
            return False
        arg_nodes = [c for c in args.children if c.is_named and c.type != "keyword_argument"]
        method = AIOHTTP[text(attr, self.src)]
        if method is None:                                          # add_route(method, path, handler)
            verb = unquote(text(arg_nodes[0], self.src)).upper() if arg_nodes and arg_nodes[0].type == "string" else ""
            method = "ANY" if verb == "*" else verb if verb in HTTP_METHODS else None
            if method is None:
                return False
            arg_nodes = arg_nodes[1:]
        if len(arg_nodes) < 2 or arg_nodes[0].type != "string":
            return False
        p = "/" if unquote(text(arg_nodes[0], self.src)).strip() == "/" else self.route_path(arg_nodes[0], recv, n)
        if p is None or not p.startswith("/"):
            return False
        self.add_endpoint(n, method, p, "aiohttp", arg_nodes[1])
        return True

    def _mount(self, n: Node, fn: Node, args: Node) -> bool:
        """`app.include_router(router, prefix="/v1")`, `app.register_blueprint(bp, url_prefix="/admin")`, Starlette's
        `app.mount("/api/v1", app=api)` — of a router of this file, or of one imported (`tag_router`,
        `users.router`), which `compose` follows to its file."""
        verb = text(fn.child_by_field_name("attribute"), self.src)
        if verb not in ("include_router", "register_blueprint", "mount", "add_namespace"):
            return False
        parent = text(fn.child_by_field_name("object"), self.src).split(".")[-1]
        pos = [a for a in args.children if a.is_named and a.type != "keyword_argument"]
        kw = {text(a.child_by_field_name("name"), self.src): a.child_by_field_name("value")
              for a in args.children if a.type == "keyword_argument"}
        if verb == "mount":
            p = self.path_of(pos[0]) if pos else None
            child = kw.get("app") or (pos[1] if len(pos) > 1 else None)
            if p is None:
                return True
        elif verb == "add_namespace":                               # api.add_namespace(ns, "/challenges")
            v = kw.get("path") or (pos[1] if len(pos) > 1 else None)
            p = (self.path_of(v) or "") if v is not None else ""
            child = pos[0] if pos else None
        else:
            v = kw.get("prefix") or kw.get("url_prefix")
            p = (self.path_of(v) or "") if v is not None else ""
            child = pos[0] if pos else None
        if child is None:
            return True
        if child.type == "identifier" and text(child, self.src) in self.router_vars:
            self.mount(text(child, self.src), child, parent, n, p)
            return True
        g = self._imported_router(child)
        if g is not None:
            self.foreign.append((g, self.router_key(parent, n), (self.prefix_for(parent, n) or "").rstrip("/") + p))
        return True

    # -- routers other files name: module variables, router parameters, returned routers ----------------------
    def read_imports(self) -> dict[str, tuple[str, str | None]]:
        """`from app.tag.views import router as tag_router` → tag_router: ("app.tag.views", "router");
        `from . import users` → users: (".", "users"); `import a.b as c` → c: ("a.b", None)."""
        out: dict[str, tuple[str, str | None]] = {}
        for n in walk(self.fx.tree.root_node):
            if n.type not in ("import_from_statement", "import_statement"):
                continue
            mod = n.child_by_field_name("module_name")
            for c in n.children_by_field_name("name"):
                alias = c.child_by_field_name("alias") if c.type == "aliased_import" else None
                name = text(c.child_by_field_name("name") if alias is not None else c, self.src)
                if n.type == "import_from_statement" and mod is not None:
                    out[text(alias, self.src) if alias is not None else name] = (text(mod, self.src), name)
                elif alias is not None:
                    out[text(alias, self.src)] = (name, None)
        return out

    def _module(self, spec: str, name: str | None) -> str | None:
        """The file a module reference names: `spec` itself, or `name` as a submodule of it."""
        if name is None:
            return self.resolve_import(spec)
        return self.resolve_import(spec + name if spec.endswith(".") else f"{spec}.{name}")

    def _imported_router(self, n: Node) -> str | None:
        """`tag_router` (imported by name) or `users.router` (`users` an imported module): the router's global id."""
        if n.type == "identifier":
            spec, orig = self.imports.get(text(n, self.src)) or (None, None)
            if spec is None or orig is None or self._module(spec, orig) is not None:
                return None                                     # a module, not a router
            target = self.resolve_import(spec)
            return f"var:{target}:{orig}" if target is not None and target.endswith(".py") else None
        obj, attr = n.child_by_field_name("object"), n.child_by_field_name("attribute")
        if n.type != "attribute" or obj is None or attr is None or obj.type != "identifier":
            return None
        spec, orig = self.imports.get(text(obj, self.src)) or (None, None)
        target = self._module(spec, orig) if spec is not None else None
        return f"var:{target}:{text(attr, self.src)}" if target is not None and target.endswith(".py") else None

    def global_of(self, key: tuple[int, str]) -> str | None:
        scope, name = key
        path = self.fx.file.path
        if scope == 0:
            if not re.fullmatch(r"[A-Za-z_]\w*", name):
                return None
            if self.module_binds(name):
                return f"var:{path}:{name}"
            spec, orig = self.imports.get(name) or (None, None)
            target = self.resolve_import(spec) if spec is not None and orig is not None else None
            return f"var:{target}:{orig}" if target is not None and target.endswith(".py") else None
        fn = self.function_of(scope)
        if fn is None or fn.type != "function_definition":
            return None
        fname = text(fn.child_by_field_name("name"), self.src)
        i = self._param(fn, name)[0]
        if i is not None:
            return f"param:{path}:{fname}:{i}"
        return f"ret:{path}:{fname}" if self.returns_name(fn, name) else None

    def router_param_type(self, fn: Node, name: str) -> str | None:
        decl = self._param(fn, name)[1] if fn.type == "function_definition" else None
        typ = decl.child_by_field_name("type") if decl is not None else None
        return text(typ, self.src) if typ is not None else "" if decl is not None else None

    def _param(self, fn: Node, name: str) -> tuple[int | None, Node | None]:
        """Position of the positional parameter `name` of `fn`, and its declaration."""
        params = fn.child_by_field_name("parameters")
        i = 0
        for d in params.named_children if params is not None else ():
            if d.type not in ("identifier", "typed_parameter", "default_parameter", "typed_default_parameter"):
                continue
            ident = d if d.type == "identifier" else d.child_by_field_name("name") or \
                next((c for c in d.children if c.type == "identifier"), None)
            if ident is not None and text(ident, self.src) == name:
                return i, d
            i += 1
        return None, None

    def _router_arguments(self, n: Node, fn: Node, args: Node) -> None:
        """`register_routes(app)`, `init_app(app)`: a router handed to a function of this file or an imported one."""
        fname = text(fn, self.src)
        if any(s.kind == "function" for s in self.symbols_by_name.get(fname, ())):
            unit = self.fx.file.path
        else:
            spec, orig = self.imports.get(fname) or (None, None)
            unit = self.resolve_import(spec) if spec is not None and orig is not None else None
            fname = orig or fname
        if unit is None:
            return
        pos = [a for a in args.children if a.is_named and a.type != "keyword_argument"]
        for i, a in enumerate(pos):
            if a.type == "identifier":
                self.router_args.append((f"param:{unit}:{fname}:{i}", text(a, self.src), n, ""))

    def _call(self, n: Node) -> None:
        fn = n.child_by_field_name("function")
        args = n.child_by_field_name("arguments")
        if fn is None or args is None:
            return
        if fn.type == "identifier":
            self._router_arguments(n, fn, args)
        if fn.type == "call":
            self._applied_decorator(n, fn, args)
        elif not self._aiohttp(n, fn, args):
            self._plain_call(n, fn, args)

    def _applied_decorator(self, n: Node, fn: Node, args: Node) -> None:
        """`router.post("/register")(register_user)`: the decorator applied by hand."""
        pos = [a for a in args.children if a.is_named and a.type != "keyword_argument"]
        if len(pos) == 1 and pos[0].type in ("identifier", "attribute"):
            self._registration(fn, n, text(pos[0], self.src).split(".")[-1])

    def _plain_call(self, n: Node, fn: Node, args: Node) -> None:
        """A mount, an outbound call, or a call that may hand a client wrapper its path."""
        if fn.type != "attribute":
            self.wrapped_call(n, fn, args)
            return
        if self._mount(n, fn, args):
            return
        callee = self.callee_of(fn)
        name, _, recv_last = split_callee(callee)
        if self._app_call(recv_last):
            return                                                  # app.get(...) used imperatively, a test client
        if self._client_call(name, recv_last):
            self._outbound(n, args, callee, name)
        else:
            self.wrapped_call(n, fn, args)

    def _app_call(self, recv_last: str) -> bool:
        return recv_last in self.router_vars or recv_last in ("app", "router", "bp", "blueprint", "api") \
            or recv_last in self.test_clients

    @staticmethod
    def _client_call(name: str, recv_last: str) -> bool:
        if name not in OUTBOUND or name not in VERB_BY_NAME and name != "request":
            return False
        return bool(CLIENT_RECEIVER.search(recv_last)
                    or recv_last in ("requests", "httpx", "session", "client", "urllib3", "http"))

    def _outbound(self, n: Node, args: Node, callee: str, name: str) -> None:
        """The first argument with a path is the call's; with no segment of its own, the function around the call may
        be a client wrapper."""
        arg_nodes = [c for c in args.children if c.is_named]
        method = OUTBOUND.get(name) or self.method_from_args(arg_nodes)
        for a in arg_nodes:
            if a.type == "keyword_argument":
                if text(a.child_by_field_name("name"), self.src) not in ("url", "path"):
                    continue
                a = a.child_by_field_name("value")
            p = self.path_of(a, lenient=True)
            if p is not None:
                if not self.add_call(n, method, p, callee):
                    self.publish_wrapper(n, method, name, arg_nodes)
                return
        self.publish_wrapper(n, method, name, arg_nodes)
