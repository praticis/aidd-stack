"""Go: net/http (>= 1.22 method patterns), gorilla `.Methods()`, chi, gin/echo (+Group), fiber routes;
net/http / resty / PostJSON-like helpers outbound."""

from __future__ import annotations

import re

from tree_sitter import Node

from ...core.http_base import (BaseScanner, CLIENT_RECEIVER, GENERIC_OUTBOUND, HANDLER_NODES, OUTBOUND, STRING_NODES,
                               first_string, text, walk)
from ...core.paths import HTTP_METHODS, VERB_BY_NAME, unquote

GO_VERB_ALIASES = {"Del": "DELETE"}                                                       # prometheus/common/route
GO_REGISTRARS = {"HandleFunc", "Handle", "Any", "Match", "All"} | set(VERB_BY_NAME) | set(GO_VERB_ALIASES)   # net/http, gorilla, chi, gin, echo, fiber
GO_MOUNTS = {"Group", "PathPrefix", "Route", "Mount", "Subrouter"}                       # prefix carriers
GO_APPS = re.compile(r"^(gin\.(Default|New)|echo\.New|fiber\.New|http\.NewServeMux)$")       # always the application
GO_ROUTERS = re.compile(r"^(chi\.(NewRouter|NewMux)|mux\.NewRouter)$")                     # the application when main builds it


class GoScanner(BaseScanner):
    relative_on_groups = True
    def run(self) -> None:
        self.servemux_vars: set[str] = set()     # net/http ServeMux: a pattern ending in "/" is a whole subtree
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
                # gin/echo/fiber build the application; a chi/gorilla router is the application only when main
                # builds it — a helper that builds one returns it to be mounted somewhere else.
                is_app = bool(GO_APPS.match(fname)) or (bool(GO_ROUTERS.match(fname)) and self._in_main(n))
                for nm in names:
                    self.router_vars.add(nm)
                    if is_app:
                        self.mark_app(nm, n)
                    if fname == "http.NewServeMux":
                        self.servemux_vars.add(nm)

    def _call(self, n: Node) -> None:
        fn = n.child_by_field_name("function")
        args = n.child_by_field_name("arguments")
        if fn is None or args is None:
            return
        callee = re.sub(r"\s+", "", text(fn, self.src))          # `client.\n\tGet(...)`
        name = callee.split(".")[-1]
        recv = callee.rsplit(".", 1)[0] if "." in callee else ""
        recv_last = recv.split(".")[-1]
        arg_nodes = [c for c in args.children if c.is_named]
        if not arg_nodes:
            return
        if self.convention_call(n, name, recv_last, callee, arg_nodes):
            return
        operand = fn.child_by_field_name("operand") if fn.type == "selector_expression" else None
        base = self._middleware_base(operand) if operand is not None else None
        if base is not None:                                        # r.With(paginate).Get("/", h): a route on r
            recv_last = base
        chain = self._chain_prefix(operand) if operand is not None and base is None else None
        if chain is not None:                                       # g.Group("/user").Use(mw).POST("", h)
            recv_last = text(operand, self.src)
            self.group_prefix[recv_last] = chain
            self.router_vars.add(recv_last)
        default_mux = recv == "http" and name in ("Handle", "HandleFunc")   # http.Handle("/x", h): the default ServeMux
        if name == "Mount" and len(arg_nodes) >= 2 and recv_last:        # chi: r.Mount("/admin", adminRouter())
            p = self.path_of(arg_nodes[0])
            child = self._router_of(arg_nodes[1])
            if p is not None and child is not None:
                self.mount_edges.append((child, self.router_key(recv_last, n), (self.prefix_for(recv_last, n) or "").rstrip("/") + p))
                return

        # ---- exposed routes ---------------------------------------------------------------
        # a receiver this file built as a router/group is one, whatever its name (`api := r.Group("/api")`)
        if name in GO_REGISTRARS and len(arg_nodes) >= 2 and (recv_last in self.router_vars or default_mux or not CLIENT_RECEIVER.search(recv_last)):
            first = arg_nodes[0]
            raw_first = unquote(text(first, self.src)) if first.type in STRING_NODES else None
            lit = raw_first if raw_first and re.match(r"^[A-Z]+ /", raw_first) else self.route_path(first, recv_last, n)
            method = VERB_BY_NAME.get(name) or GO_VERB_ALIASES.get(name) or (None if name in ("HandleFunc", "Handle", "Match") else "ANY")
            if name == "Match" and len(arg_nodes) >= 3:                 # gin: r.Match([]string{...}, "/x", h)
                lit = self.route_path(arg_nodes[1], recv_last, n)
            if name == "Handle" and (default_mux or recv_last in self.servemux_vars) and lit and len(lit) > 1 and lit.endswith("/"):
                return                                                  # mux.Handle("/booking/v1/", sub): a mount, not a route
            if lit and (lit.startswith("/") or re.match(r"^[A-Z]+ /", lit)):
                handler = arg_nodes[-1]
                if self.is_handler_like(handler) or recv_last in self.router_vars or name in ("HandleFunc", "Handle"):
                    framework = "net/http"
                    if name in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "Any", "Match"):
                        framework = "gin/echo"
                    elif name in ("Get", "Post", "Put", "Patch", "Delete", "Head", "Options", "All") or name in GO_VERB_ALIASES:
                        framework = "chi/fiber"
                    if method is None:
                        gm = self._gorilla_methods(n)
                        if gm:
                            method, framework = gm, "gorilla"
                    self.add_endpoint(n, method or "ANY", lit, framework, handler, prefix=self.prefix_for(recv_last, n) or "",
                                      router=recv_last)
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

    def _middleware_base(self, n: Node) -> str | None:
        """`r.With(mw).Use(mw2)` — only middleware on a variable: that variable's name (None for any other receiver)."""
        if n.type != "call_expression":
            return None
        while n.type == "call_expression":
            fn = n.child_by_field_name("function")
            if fn is None or fn.type != "selector_expression" or text(fn.child_by_field_name("field"), self.src) not in ("Use", "With"):
                return None
            n = fn.child_by_field_name("operand")
        return text(n, self.src) if n.type == "identifier" else None

    def _chain_prefix(self, n: Node) -> str | None:
        """The prefix a receiver chain carries — `g.Group("/user").Use(mw)` → "/user" (plus g's own); None when the
        chain holds no group."""
        if n.type != "call_expression":
            return None
        fn = n.child_by_field_name("function")
        args = n.child_by_field_name("arguments")
        if fn is None or args is None or fn.type != "selector_expression":
            return None
        field, operand = fn.child_by_field_name("field"), fn.child_by_field_name("operand")
        if field is None or operand is None:
            return None
        verb = text(field, self.src)
        if verb in ("Use", "With"):                                     # middleware: same prefix
            return self._chain_prefix(operand)
        if verb != "Group":
            return None
        arg_nodes = [c for c in args.children if c.is_named]
        p = self.path_of(arg_nodes[0]) if arg_nodes else None
        if p is None:
            return None
        inner = self._chain_prefix(operand)
        base = inner if inner is not None else (self.prefix_for(text(operand, self.src).split(".")[-1], n) or "")
        return base.rstrip("/") + p

    def region_of(self, call: Node, fn: Node) -> tuple[str, str, bool] | None:
        """chi/fiber `r.Route("/x", func(r chi.Router) {...})`, chi `r.Group(func(r chi.Router) {...})` and gitea's
        `m.Group("/x", func() { m.Get(...) })` — the closure's routes live under the prefix."""
        callee = call.child_by_field_name("function")
        args = call.child_by_field_name("arguments")
        if callee is None or args is None or callee.type != "selector_expression":
            return None
        verb = text(callee.child_by_field_name("field"), self.src)
        if verb not in ("Route", "Group"):
            return None
        outer = text(callee.child_by_field_name("operand"), self.src).split(".")[-1]
        arg_nodes = [c for c in args.children if c.is_named]
        first = arg_nodes[0] if arg_nodes else None
        p = "" if first is fn else self.path_of(first) if first is not None else None
        if p is None:
            return None
        return outer, p, verb == "Group"

    def _router_of(self, n: Node) -> tuple[int, str] | None:
        """The router a Mount argument names: a variable, or the variable a function of this file returns."""
        if n.type == "identifier":
            return self.router_key(text(n, self.src), n)
        if n.type != "call_expression" or n.child_by_field_name("function") is None:
            return None
        fname = text(n.child_by_field_name("function"), self.src)
        for d in walk(self.fx.tree.root_node):
            if d.type == "function_declaration" and text(d.child_by_field_name("name"), self.src) == fname:
                for r in walk(d):
                    if r.type == "return_statement":
                        ids_ = [c for c in walk(r) if c.type == "identifier"]
                        if len(ids_) == 1:
                            return self.router_key(text(ids_[0], self.src), ids_[0])
                return None
        return None

    def _in_main(self, n: Node) -> bool:
        p = n.parent
        while p is not None and p.type not in ("function_declaration", "method_declaration", "func_literal"):
            p = p.parent
        name = p.child_by_field_name("name") if p is not None and p.type == "function_declaration" else None
        return name is not None and text(name, self.src) == "main"

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

