"""Go: net/http (>= 1.22 method patterns), gorilla `.Methods()`, chi, gin/echo (+Group), fiber routes;
net/http / resty / PostJSON-like helpers outbound."""

from __future__ import annotations

import re

from tree_sitter import Node

from ...core.http_base import (BaseScanner, CLIENT_RECEIVER, GENERIC_OUTBOUND, HANDLER_NODES, OUTBOUND, STRING_NODES,
                               first_string, text, walk)
from ...core.paths import HTTP_METHODS, VERB_BY_NAME, unquote

GO_REGISTRARS = {"HandleFunc", "Handle", "Any", "Match", "All"} | set(VERB_BY_NAME)      # net/http, gorilla, chi, gin, echo, fiber
GO_MOUNTS = {"Group", "PathPrefix", "Route", "Mount", "Subrouter"}                       # prefix carriers


class GoScanner(BaseScanner):
    def run(self) -> None:
        for n in walk(self.fx.tree.root_node):
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
        names = [text(c, self.src) for c in (left.children if left.type == "expression_list" else [left]) if c.type == "identifier"]
        for r in rights:
            if r.type != "call_expression":
                continue
            fn = r.child_by_field_name("function")
            if fn is None:
                continue
            fname = text(fn, self.src)
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
        callee = text(fn, self.src)
        name = callee.split(".")[-1]
        recv = callee.rsplit(".", 1)[0] if "." in callee else ""
        recv_last = recv.split(".")[-1]
        arg_nodes = [c for c in args.children if c.is_named]
        if not arg_nodes:
            return

        # ---- exposed routes ---------------------------------------------------------------
        if name in GO_REGISTRARS and len(arg_nodes) >= 2 and not CLIENT_RECEIVER.search(recv_last):
            first = arg_nodes[0]
            raw_first = unquote(text(first, self.src)) if first.type in STRING_NODES else None
            lit = raw_first if raw_first and re.match(r"^[A-Z]+ /", raw_first) else self.path_of(first)
            method = VERB_BY_NAME.get(name) if name in VERB_BY_NAME else (None if name in ("HandleFunc", "Handle", "Match") else "ANY")
            if name == "Match" and len(arg_nodes) >= 3:                 # gin: r.Match([]string{...}, "/x", h)
                lit = self.path_of(arg_nodes[1])
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
        if fld is None or text(fld, self.src) != "Methods":
            return None
        outer = p.parent
        if outer is None or outer.type != "call_expression":
            return None
        args = outer.child_by_field_name("arguments")
        return self.method_from_args([c for c in args.children if c.is_named]) if args else None

