"""TypeScript / JavaScript: express / koa / fastify (`app.get('/x', handler)`) + NestJS decorators;
axios / fetch / got / ky outbound."""

from __future__ import annotations

import re

from tree_sitter import Node

from ...core.http_base import (BaseScanner, CLIENT_RECEIVER, GENERIC_OUTBOUND, OUTBOUND, Region, split_callee,
                               text, walk)
from ...core.paths import VERB_BY_NAME

TS_REGISTRARS = {"get", "post", "put", "patch", "delete", "head", "options", "all", "route"}
TS_VERB_ALIASES = {"del": "DELETE"}                                       # superagent, NodeBB's api module
JQUERY = {"$", "jQuery"}
JQUERY_VERBS = {"get": "GET", "post": "POST", "getJSON": "GET"}             # $.get(url, data?, success?)


class TsScanner(BaseScanner):
    """express / koa / fastify (`app.get('/x', handler)`) + NestJS decorators."""

    def run(self) -> None:
        controller_prefix: dict[int, str] = {}
        for n in walk(self.fx.tree.root_node):
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
        if re.search(r"\b(express|Router|Fastify|fastify|Koa|new Hono|Hono|new Elysia|Elysia)\s*\(", txt) or re.search(r"\.(Router|router)\(\)", txt):
            self.router_vars.add(nm)
            if re.match(r"^(express|fastify|Fastify)\s*\(", txt):           # the application, not an express.Router()
                self.mark_app(nm, n)

    def _mount(self, n: Node, name: str, recv_last: str, arg_nodes: list[Node]) -> bool:
        """express/koa `app.use('/api', router)`, Hono `app.route('/book', book)`: a router of this file under a prefix."""
        if name not in ("use", "route") or len(arg_nodes) < 2 or not recv_last:
            return False
        p = self.path_of(arg_nodes[0])
        if p is None or not p.startswith("/"):
            return False
        children = [a for a in arg_nodes[1:] if a.type == "identifier" and text(a, self.src) in self.router_vars]
        if name == "route" and (len(arg_nodes) != 2 or not children):
            return False                                           # express app.route('/x').get(h)
        for c in children:
            self.mount(text(c, self.src), c, recv_last, n, p)
        return bool(children)

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

    def _decorator(self, n: Node, controller_prefix: dict[int, str]) -> None:
        txt = text(n, self.src)
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
        callee = self.callee_of(fn)
        name, recv, recv_last = split_callee(callee)
        arg_nodes = [c for c in args.children if c.is_named]
        if not arg_nodes:
            return
        if "getHttpServer" in callee or "supertest" in callee or "request(app" in callee:
            return                                                  # supertest-style test clients
        if self.convention_call(n, name, recv_last, callee, arg_nodes):
            return
        if self._mount(n, name, recv_last, arg_nodes):
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

