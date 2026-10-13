"""TypeScript / JavaScript: express / koa / fastify (`app.get('/x', handler)`) + NestJS decorators;
axios / fetch / got / ky outbound."""

from __future__ import annotations

import re

from tree_sitter import Node

from ...core.http_base import (BaseScanner, CLIENT_RECEIVER, GENERIC_OUTBOUND, HANDLER_NODES, OUTBOUND, STRING_NODES,
                               first_string, text, walk)
from ...core.paths import HTTP_METHODS, VERB_BY_NAME, unquote

TS_REGISTRARS = {"get", "post", "put", "patch", "delete", "head", "options", "all", "route"}


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
        if re.search(r"\b(express|Router|Fastify|fastify|Koa|new Hono|Hono|new Elysia|Elysia)\s*\(", txt) or re.search(r"\.(Router|router)\(\)", txt):
            self.router_vars.add(text(name, self.src))

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
        callee = text(fn, self.src)
        name = callee.split(".")[-1]
        recv = callee.rsplit(".", 1)[0] if "." in callee else ""
        recv_last = recv.split(".")[-1]
        arg_nodes = [c for c in args.children if c.is_named]
        if not arg_nodes:
            return
        if "getHttpServer" in callee or "supertest" in callee or "request(app" in callee:
            return                                                  # supertest-style test clients
        if self.convention_call(n, name, recv_last, callee, arg_nodes):
            return
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

