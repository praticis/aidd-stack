"""The app's own HTTP client wrappers in Python. A function or method whose outbound call builds its path around one of
its parameters is a wrapper: `_request(self, method, path)` doing `self.client.request(method, path)`, or `api_get(path)`
doing `requests.get(BASE_URL + path)`. A call that hands it a literal path is an outbound call
(`self._request("GET", "/v1/orders")`); a call that hands it a parameter of its own function makes that function a
wrapper too (`_get(self, path)` doing `self._request("GET", path)`). A call on a receiver reaches the wrapper of the
class the type index finds declaring the method, up the MRO of the type the resolver gives the receiver, named as the index
names it (`app/clients:Client`); a plain name is a function of the module or imported."""

from __future__ import annotations

from tree_sitter import Node

from ...core.http_base import HttpResult, Pending, text
from ...core.http_nodes import has_interpolation
from ...core.http_scope import enclosing_function
from ...core.http_wrappers import (PARAM, WrappedCall, WrapperShape, compose_wrapped_calls as compose_calls, param_shape,
                                   verb_of)
from ...core.paths import HTTP_METHODS, has_literal_segment, normalize_path, unquote
from .declared import owner
from .forms import path as class_path
from .modules import module_path
from .type_index import qualified

SCOPE = "py"                       # the scope of the wrapper facts the core's machinery composes for Python
URL_KEYWORDS = ("url", "path")


class PyClientWrappers:
    """Mixin of the Python scanner: publishes wrappers, and keeps the calls to wrappers pending."""

    def publish_wrapper(self, call: Node, method: str | None, name: str, arg_nodes: list[Node]) -> None:
        """`call`, an outbound call (`name`) whose path is built around a parameter of the function around it: that
        function is a client wrapper, with the call's verb or the parameter the call takes it from."""
        key, params = self.function_key(call)
        if key is None:
            return
        urls, verb = self._wrapper_args(name, arg_nodes)
        shape = next((sh for a in urls if (sh := param_shape(self, a, params)) is not None), None)
        if shape is not None:
            vi = self._param_index(verb, params) if method is None else None
            default = self._verb_default(enclosing_function(call), params[vi]) if vi is not None else None
            verb_given = method.upper() if method else None
            self.out.publish(key, WrapperShape(*shape, verb_given, vi, tuple(params), default), SCOPE)

    def _wrapper_args(self, name: str, arg_nodes: list[Node]) -> tuple[list[Node], Node | None]:
        """The arguments that can be the path, and the one that is the verb of `request(method, url)`."""
        pos = [a for a in arg_nodes if a.type not in ("keyword_argument", "comment")]
        kw = {text(a.child_by_field_name("name"), self.src): a.child_by_field_name("value")
              for a in arg_nodes if a.type == "keyword_argument"}
        urls = [v for k, v in kw.items() if k in URL_KEYWORDS and v is not None]
        if name == "request":
            return pos[1:2] + urls, (pos[0] if pos else kw.get("method"))
        return pos[:1] + urls, None

    def _param_index(self, n: Node | None, params: list[str]) -> int | None:
        name = text(n, self.src) if n is not None and n.type == "identifier" else None
        return params.index(name) if name in params else None

    def _verb_default(self, fn: Node, name: str) -> str | None:
        """The verb a parameter defaults to (`method: str = 'POST'`), when the call does not pass one."""
        params = fn.child_by_field_name("parameters")
        for d in params.named_children if params is not None else ():
            ident, value = d.child_by_field_name("name"), d.child_by_field_name("value")
            if d.type in ("default_parameter", "typed_default_parameter") and ident is not None and value is not None \
                    and text(ident, self.src) == name and value.type == "string":
                return verb_of(unquote(text(value, self.src)))
        return None

    def function_key(self, at: Node) -> tuple[str | None, list[str]]:
        """The wrapper key of the function around `at` (`app/clients:Client.method`, or `<file>:function` at module
        level) and its positional parameters, without the `self` or `cls` of a method."""
        fn = enclosing_function(at)
        name = fn.child_by_field_name("name") if fn is not None and fn.type == "function_definition" else None
        if name is None:
            return None, []
        params = self._positional(fn)
        if _at_module_level(fn):
            return f"{self.fx.file.path}:{text(name, self.src)}", params
        cls = self._class_of(fn)
        if cls is None:
            return None, []
        rest = params[1:] if params[:1] in (["self"], ["cls"]) else params
        return f"{cls}.{text(name, self.src)}", rest

    def _class_of(self, fn: Node) -> str | None:
        """The class whose method `fn` is, named as the type index names it; None for one a function holds."""
        index = self.scopes.python
        scope = next((s for s in index.scopes if s.node.id == fn.id), None)
        cls = owner(scope) if scope is not None else None
        found = class_path(index, cls) if cls is not None else None
        return f"{module_path(self.fx.file)}:{found}" if isinstance(found, str) and found else None

    def _positional(self, fn: Node) -> list[str]:
        params = fn.child_by_field_name("parameters")
        out = []
        for d in params.named_children if params is not None else ():
            ident = d if d.type == "identifier" else None
            if d.type in ("typed_parameter", "default_parameter", "typed_default_parameter"):
                ident = d.child_by_field_name("name") or next((c for c in d.children if c.type == "identifier"), None)
            if ident is not None:
                out.append(text(ident, self.src))
        return out

    # -- the calls that may hand a wrapper its path ---------------------------------------------------------------
    def wrapped_call(self, n: Node, fn: Node, args: Node) -> None:
        """A call on a receiver of a class of the repo, or to a function of the module or imported, with an argument
        that can be a path: it waits for `compose`, which knows every wrapper of the repo."""
        target = self._target(fn, n)
        if target is None:
            return
        outer = self.function_key(n)
        pos = [a for a in args.named_children if a.type not in ("keyword_argument", "comment")]
        kws = [a for a in args.named_children if a.type == "keyword_argument"]
        values = tuple(self._value(a, outer[1]) for a in pos)
        named = tuple((text(k.child_by_field_name("name"), self.src), self._value(k.child_by_field_name("value"), outer[1]))
                      for k in kws)
        item = self.call_info(n, None, "", text(fn, self.src)) if any(values) or any(v for _, v in named) else None
        if item is not None:
            call = WrappedCall(target, values, named, outer[0], tuple(outer[1]))
            self.out.pending.append(Pending(item, call, SCOPE))

    def _value(self, a: Node | None, params: list[str]) -> str | tuple | None:
        """A literal path or verb, or the parameter of the function around the call the argument is built around."""
        if a is None:
            return None
        p = self.path_of(a, lenient=True)
        if p is not None and has_literal_segment(normalize_path(p)):
            return p
        shape = param_shape(self, a, params) if params else None
        if shape is not None:
            return (PARAM, *shape)
        verb = unquote(text(a, self.src)) if a.type == "string" and not has_interpolation(a) else ""
        return verb if verb.upper() in HTTP_METHODS else None

    def _target(self, fn: Node, at: Node) -> tuple | None:
        if fn.type == "identifier":
            return self._function_target(text(fn, self.src))
        declaring = self.declaring(at, fn) if fn.type == "attribute" else None
        if declaring is None or not declaring.name:
            return None
        return "class", qualified(declaring), text(fn.child_by_field_name("attribute"), self.src)

    def _function_target(self, name: str) -> tuple | None:
        if any(s.kind == "function" for s in self.symbols_by_name.get(name, ())):
            return ("func", f"{self.fx.file.path}:{name}")
        spec, orig = self.imports.get(name) or (None, None)
        unit = self.resolve_import(spec) if spec is not None and orig is not None else None
        return ("func", f"{unit}:{orig}") if unit else None


def compose_wrapped_calls(out: HttpResult) -> None:
    compose_calls(out, SCOPE)


def _at_module_level(fn: Node) -> bool:
    p = fn.parent
    p = p.parent if p is not None and p.type == "decorated_definition" else p
    return p is not None and p.type == "module"
