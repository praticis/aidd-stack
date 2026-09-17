"""C# / ASP.NET Core: attribute-routed controllers + minimal APIs (MapGroup chains);
HttpClient.*Async, HttpRequestMessage, Refit, Flurl, RestSharp outbound."""

from __future__ import annotations

import re

from tree_sitter import Node

from ...core.http_base import (BaseScanner, CLIENT_RECEIVER, GENERIC_OUTBOUND, HANDLER_NODES, OUTBOUND, STRING_NODES,
                               first_string, text, walk)
from ...core.paths import HTTP_METHODS, VERB_BY_NAME, unquote

CS_MAP = {"MapGet": "GET", "MapPost": "POST", "MapPut": "PUT", "MapPatch": "PATCH", "MapDelete": "DELETE", "MapMethods": None, "Map": "ANY"}
CS_HTTP_ATTR = {"HttpGet": "GET", "HttpPost": "POST", "HttpPut": "PUT", "HttpPatch": "PATCH", "HttpDelete": "DELETE", "HttpHead": "HEAD", "HttpOptions": "OPTIONS"}
FLURL_VERBS = {"GetAsync": "GET", "GetJsonAsync": "GET", "GetStringAsync": "GET", "GetStreamAsync": "GET",
               "PostAsync": "POST", "PostJsonAsync": "POST", "PostStringAsync": "POST", "PostUrlEncodedAsync": "POST",
               "PutAsync": "PUT", "PutJsonAsync": "PUT", "PatchAsync": "PATCH", "PatchJsonAsync": "PATCH",
               "DeleteAsync": "DELETE", "HeadAsync": "HEAD", "OptionsAsync": "OPTIONS"}


class CsScanner(BaseScanner):
    """ASP.NET Core: attribute-routed controllers + minimal APIs; HttpClient / Refit outbound."""

    def run(self) -> None:
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

    def _controller(self, cls: Node) -> None:
        prefixes = [lit for name, lit, _ in self._attrs(cls) if name in ("Route", "RoutePrefix") and lit is not None]
        cname = cls.child_by_field_name("name")
        cname_txt = text(cname, self.src) if cname is not None else ""
        controller = re.sub(r"Controller$", "", cname_txt)
        body = cls.child_by_field_name("body")
        if body is None:
            return
        is_controller = bool(prefixes) or cname_txt.endswith("Controller") or any(name == "ApiController" for name, _, _ in self._attrs(cls))
        if not is_controller:
            return
        prefix = prefixes[0] if prefixes else ""
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
            for method, lit, a in routes:
                tmpl = lit if lit is not None else (extra[0] if extra else "")
                full = tmpl if (tmpl.startswith("/") or tmpl.startswith("~/")) else (prefix.rstrip("/") + "/" + tmpl).rstrip("/")
                full = full.replace("~/", "/")
                full = re.sub(r"\[controller\]", controller.lower(), full, flags=re.I)
                full = re.sub(r"\[action\]", (hname or "").lower(), full, flags=re.I)
                self.add_endpoint(a, method, full or "/", "aspnet", None, handler_name=hname, handler_id=hid)

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

    def _invocation(self, n: Node) -> None:
        kids = [c for c in n.children if c.is_named]
        if len(kids) < 2 or kids[-1].type != "argument_list":
            return
        fn, args = kids[0], kids[-1]
        callee = text(fn, self.src)
        callee = re.sub(r"<[^<>]*>", "", callee)                   # GetFromJsonAsync<T>
        name = callee.split(".")[-1]
        recv_last = (callee.rsplit(".", 1)[0] if "." in callee else "").split(".")[-1]
        arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named]
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
            p = self.path_of(arg_nodes[0])
            if p is not None and (self.is_handler_like(arg_nodes[-1]) or True):
                method = CS_MAP[name]
                if name == "MapMethods":
                    method = self.method_from_args(arg_nodes[1:2]) or "ANY"
                self.add_endpoint(n, method or "ANY", p, "aspnet-minimal", arg_nodes[-1], prefix=self.group_prefix.get(recv_last, ""))
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

