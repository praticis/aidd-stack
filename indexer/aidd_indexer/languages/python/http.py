"""Python: FastAPI (APIRouter prefix) / Flask (Blueprint url_prefix) / Starlette decorators;
requests / httpx / aiohttp outbound."""

from __future__ import annotations

import re

from tree_sitter import Node

from ...core.http_base import (BaseScanner, CLIENT_RECEIVER, GENERIC_OUTBOUND, HANDLER_NODES, OUTBOUND, STRING_NODES,
                               first_string, text, walk)
from ...core.paths import HTTP_METHODS, VERB_BY_NAME, unquote

PY_REGISTRARS = {"get", "post", "put", "patch", "delete", "head", "options", "route", "api_route", "websocket"}


class PyScanner(BaseScanner):
    """FastAPI / Flask / Starlette decorators; requests / httpx / aiohttp outbound."""

    def run(self) -> None:
        for n in walk(self.fx.tree.root_node):
            if n.type == "assignment":
                self._maybe_router(n)
        for n in walk(self.fx.tree.root_node):
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
        fname = text(fn, self.src).split(".")[-1] if fn is not None else ""
        if fname in ("APIRouter", "Blueprint", "FastAPI", "Flask", "Starlette", "Router", "Sanic", "Quart"):
            name = text(left, self.src)
            self.router_vars.add(name)
            args = right.child_by_field_name("arguments")
            prefix = ""
            if args is not None:
                for a in args.children:
                    if a.type == "keyword_argument" and text(a.child_by_field_name("name"), self.src) in ("prefix", "url_prefix"):
                        v = a.child_by_field_name("value")
                        prefix = unquote(text(v, self.src)) if v is not None and v.type == "string" else ""
            self.group_prefix[name] = prefix

    def _decorated(self, n: Node) -> None:
        func = next((c for c in n.children if c.type in ("function_definition", "class_definition")), None)
        fname_node = func.child_by_field_name("name") if func is not None else None
        hname = text(fname_node, self.src) if fname_node is not None else None
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
            recv = text(fn.child_by_field_name("object"), self.src).split(".")[-1]
            verb = text(fn.child_by_field_name("attribute"), self.src)
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
                    if a.type == "keyword_argument" and text(a.child_by_field_name("name"), self.src) == "methods":
                        found = re.findall(r"[\"']([A-Za-z]+)[\"']", text(a.child_by_field_name("value"), self.src))
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
        callee = text(fn, self.src)
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
                if text(a.child_by_field_name("name"), self.src) not in ("url", "path"):
                    continue
                a = a.child_by_field_name("value")
            p = self.path_of(a, lenient=True)
            if p is not None:
                self.add_call(n, method, p, callee)
                return
