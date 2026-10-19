"""How TS/JS paths built by code read: a call to a function of the file, or to a method of the class around it, is the
path it returns (`apiRoot()` with `function apiRoot() { return toAbsURL('/api/v1') }`, `itemUrl(id)` returning
`` `/catalog/items/${id}` ``); and an unknown start of a path is a base URL, unless it is a link read from the page."""

from __future__ import annotations

from tree_sitter import Node

from ...core.http_base import text, unwrap_arg, valid_path, walk
from ...core.http_nodes import CLASS_NODES, member
from ...core.http_wrappers import continues_path, param_shape
from ...core.paths import unquote

PATH_MODULES = ("path", "node:path", "path-browserify", "path/posix")
PAGE_LINKS = frozenset({"getAttribute", "dataset", "pathname", "href", "baseURI"})     # a link the page holds


class TsReturns:
    """Mixin of the TS scanner; uses the parameter reading of `TsClientWrappers` (`_signature`, `_function_around`)."""

    def runtime_lead(self, n: Node) -> bool:
        """Whether the template or concatenation `n` starts with a link read from the page — an attribute, a dataset
        entry, a link's `pathname` or `href` (`${el.getAttribute('data-url')}/move`, `${link.pathname}/info`), also
        through a local holding one: a path on the site the code does not know, so no call. Any other unknown start
        is a base URL (a host, the app's sub-URL)."""
        lead = _lead(n)
        return lead is not None and self.path_of(lead) is None and self._page_link(lead, 0)

    def _page_link(self, e: Node, depth: int) -> bool:
        e = unwrap_arg(e)
        if depth > 3:
            return False
        if e.type == "identifier":
            bound, val = self.scopes.binding(e)
            return bound and val is not None and self._page_link(val, depth + 1)
        if e.type in ("template_string", "binary_expression"):
            lead = _lead(e)
            return lead is not None and self.path_of(lead) is None and self._page_link(lead, depth + 1)
        while e.type in ("member_expression", "call_expression", "subscript_expression", "non_null_expression",
                         "await_expression", "parenthesized_expression"):
            prop = e.child_by_field_name("property") if e.type == "member_expression" else None
            if prop is not None and text(prop, self.src) in PAGE_LINKS:
                return True
            e = e.child_by_field_name("object") or e.child_by_field_name("function") or e.named_children[0]
        return False

    def returned_path(self, call: Node, lenient: bool, depth: int) -> str | None:
        """`apiRoot()` with `function apiRoot() { return toAbsURL('/api/v1') }`, `this.getUsersRoute()` with a method
        returning `` `${this.getBaseRoute()}/users` ``: the path the function returns, with its parameters as the
        call's arguments when it returns one of them (`toAbsURL(val)` returning `path.join(base, val)`)."""
        f = self._called(call.child_by_field_name("function"), call)
        e = self._returned(f) if f is not None else None
        if e is None:
            return None
        params = self._signature(f)[0]
        shape = self._returned_shape(e, params)
        if shape is None:                       # a parameter handed on to another helper is one unknown segment
            return self.path_of(e, lenient, depth + 1)
        i, before, after = shape
        args = call.child_by_field_name("arguments")
        a = [unwrap_arg(c) for c in args.named_children][i] if args is not None and i < args.named_child_count else None
        arg = (unquote(text(a, self.src)) if a.type == "string" else self.path_of(a, lenient, depth + 1)) if a else None
        if arg is None and not continues_path(shape):
            arg = "{param}"                                     # one segment the code does not know
        return valid_path(before + arg + after, lenient) if arg is not None else None

    def _returned_shape(self, e: Node, params: list[str]) -> tuple[int, str, str] | None:
        """A return built around a parameter: the parameter, a concatenation or template, or `path.join(.., p)` — the
        parts before it that the code knows, joined (a base it does not know is the base URL's)."""
        if e.type == "identifier" and text(e, self.src) in params:
            return params.index(text(e, self.src)), "", ""
        obj, prop = member(e.child_by_field_name("function")) if e.type == "call_expression" else (None, None)
        if obj is None or prop is None or text(prop, self.src) != "join" \
                or (self.imports.get(text(obj, self.src)) or (None,))[0] not in PATH_MODULES:
            return param_shape(self, e, params)
        args = [unwrap_arg(a) for a in e.child_by_field_name("arguments").named_children]
        last = args[-1] if args else None
        if last is None or last.type != "identifier" or text(last, self.src) not in params:
            return None
        known = [p.strip("/") for a in args[:-1] if (p := self.path_of(a)) is not None and p.strip("/")]
        return params.index(text(last, self.src)), ("/" + "/".join(known) if known else ""), ""

    def _returned(self, fn: Node) -> Node | None:
        """The one expression `fn` returns: an arrow's body, or its only `return`."""
        body = fn.child_by_field_name("body")
        if body is None or body.type != "statement_block":
            return unwrap_arg(body) if body is not None else None
        found = [r for r in walk(body) if r.type == "return_statement" and self._function_around(r) == fn]
        vals = [c for c in found[0].named_children if c.type != "comment"] if len(found) == 1 else []
        return unwrap_arg(vals[0]) if len(vals) == 1 else None

    def _called(self, fn: Node | None, at: Node) -> Node | None:
        """The function a call names: one of the module, or a method of the class around the call (`this.m()`)."""
        if fn is not None and fn.type == "identifier":
            return self._module_functions().get(text(fn, self.src))
        obj, prop = member(fn) if fn is not None else (None, None)
        if obj is None or prop is None or obj.type != "this":
            return None
        cls = at.parent
        while cls is not None and cls.type not in CLASS_NODES:
            cls = cls.parent
        return self._class_methods(cls).get(text(prop, self.src)) if cls is not None else None

    def _class_methods(self, cls: Node) -> dict[str, Node]:
        memo = self.__dict__.setdefault("_methods_by_class", {})
        if cls.id not in memo:
            body = cls.child_by_field_name("body")
            found: dict[str, Node] = {}
            for m in body.named_children if body is not None else ():
                name = m.child_by_field_name("name") or m.child_by_field_name("property")
                value = m if m.type == "method_definition" else m.child_by_field_name("value")
                if name is not None and value is not None and value.type in ("method_definition", "arrow_function",
                                                                             "function_expression"):
                    found.setdefault(text(name, self.src), value)
            memo[cls.id] = found
        return memo[cls.id]

    def _module_functions(self) -> dict[str, Node]:
        memo = self.__dict__.get("_functions_by_name")
        if memo is None:
            memo = self.__dict__["_functions_by_name"] = {}
            for st in self.fx.tree.root_node.named_children:
                st = st.child_by_field_name("declaration") or st if st.type == "export_statement" else st
                if st.type == "function_declaration" and st.child_by_field_name("name") is not None:
                    memo[text(st.child_by_field_name("name"), self.src)] = st
                for d in st.named_children if st.type in ("lexical_declaration", "variable_declaration") else ():
                    name, value = d.child_by_field_name("name"), d.child_by_field_name("value")
                    if name is not None and value is not None and value.type in ("arrow_function", "function_expression"):
                        memo[text(name, self.src)] = value
        return memo


def _lead(n: Node) -> Node | None:
    """The expression a template (`${x}/a`) or a concatenation (`x + "/a"`) starts with, unless it starts with text."""
    if n.type == "template_string":
        first = n.named_children[0] if n.named_child_count else None
        return first.named_children[0] if first is not None and first.type == "template_substitution" \
            and first.named_child_count == 1 else None
    while n is not None and n.type == "binary_expression":
        op = n.child_by_field_name("operator")
        if op is None or op.type != "+":
            return None
        n = n.child_by_field_name("left")
    return n if n is not None and n.type not in ("string", "template_string") else None
