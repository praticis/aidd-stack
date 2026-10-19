"""The app's own HTTP client wrappers in Python. A function or method whose outbound call builds its path around one of
its parameters is a wrapper: `_request(self, method, path)` doing `self.client.request(method, path)`, or `api_get(path)`
doing `requests.get(BASE_URL + path)`. A call that hands it a literal path is an outbound call
(`self._request("GET", "/v1/orders")`); a call that hands it a parameter of its own function makes that function a
wrapper too (`_get(self, path)` doing `self._request("GET", path)`). The receiver's class is the method's for `self`, or
a class of the repo constructed into a local or into `self.x`; a plain name is a function of the module or imported."""

from __future__ import annotations

from tree_sitter import Node

from ...core.http_base import HttpResult, Pending, text, walk
from ...core.http_nodes import has_interpolation
from ...core.http_scope import END, enclosing_function
from ...core.http_wrappers import (PARAM, WrappedCall, WrapperShape, compose_wrapped_calls as compose_calls,
                                   param_shape, verb_of)
from ...core.paths import HTTP_METHODS, has_literal_segment, normalize_path, unquote

WRAPPER = "py.client-wrapper"      # fact: wrapper key → (path index, before, after, verb, verb index, parameters,
                                   #   the verb parameter's default)
BASES = "py.class-bases"           # fact: class → its bases' names
URL_KEYWORDS = ("url", "path")


class PyClientWrappers:
    """Mixin of the Python scanner: publishes wrappers and class bases, and keeps the calls to wrappers pending."""

    def publish_bases(self, cls: Node) -> None:
        name, sup = cls.child_by_field_name("name"), cls.child_by_field_name("superclasses")
        bases = tuple(text(b, self.src).split(".")[-1] for b in (sup.named_children if sup is not None else ())
                      if b.type in ("identifier", "attribute"))
        if name is not None and bases:
            self.out.publish(BASES, text(name, self.src), bases)

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
            self.out.publish(WRAPPER, key, WrapperShape(*shape, verb_given, vi, tuple(params), default))

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
        """The wrapper key of the function around `at` (`Class.method`, or `<file>:function` at module level) and its
        positional parameters, without the `self` or `cls` of a method."""
        fn = enclosing_function(at)
        name = fn.child_by_field_name("name") if fn is not None and fn.type == "function_definition" else None
        owner = _owner_class(fn) if name is not None else None
        if name is None or owner is None and not _at_module_level(fn):
            return None, []
        params = self._positional(fn)
        if owner is None:
            return f"{self.fx.file.path}:{text(name, self.src)}", params
        rest = params[1:] if params[:1] in (["self"], ["cls"]) else params
        return f"{text(owner.child_by_field_name('name'), self.src)}.{text(name, self.src)}", rest

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
            self.out.pending.append(Pending(item, WRAPPER, call))

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
        obj, attr = fn.child_by_field_name("object"), fn.child_by_field_name("attribute")
        if fn.type != "attribute" or obj is None or attr is None:
            return None
        cls = self._class_of(obj, at)
        return ("class", cls, text(attr, self.src)) if cls else None

    def _function_target(self, name: str) -> tuple | None:
        if any(s.kind == "function" for s in self.symbols_by_name.get(name, ())):
            return ("func", f"{self.fx.file.path}:{name}")
        spec, orig = self.imports.get(name) or (None, None)
        unit = self.resolve_import(spec) if spec is not None and orig is not None else None
        return ("func", f"{unit}:{orig}") if unit else None

    def _class_of(self, obj: Node, at: Node) -> str | None:
        """The repo class a receiver is an instance of: `self` in a method, a local or module variable assigned
        `Client(..)`, or `self.client` assigned `Client(..)` in a method of the class."""
        if obj.type == "identifier" and text(obj, self.src) in ("self", "cls"):
            owner = _owner_class(enclosing_function(at))
            return text(owner.child_by_field_name("name"), self.src) if owner is not None else None
        if obj.type == "identifier":
            return self._constructed(self._value_of(obj, at))
        inner = obj.child_by_field_name("object") if obj.type == "attribute" else None
        if inner is not None and text(inner, self.src) == "self":
            return self._attribute_class(_owner_class(enclosing_function(at)), text(obj, self.src))
        return None

    def _value_of(self, ident: Node, at: Node) -> Node | None:
        """The value a name holds where it is used; a module variable seen from a function, its module assignment (a
        client built once at import)."""
        name = text(ident, self.src)
        val = self.resolve_local(ident)
        if val is None and self.scopes.binding_scope(name, at) == 0:
            val = self.scopes.assigned_before(self.scopes.root, END, name)
        return val

    def _attribute_class(self, cls: Node | None, attr: str) -> str | None:
        memo = self.__dict__.setdefault("_attribute_classes", {})
        key = (cls.id if cls is not None else None, attr)
        if key not in memo:
            memo[key] = next((c for n in (walk(cls) if cls is not None else ()) if n.type == "assignment"
                              and text(n.child_by_field_name("left"), self.src) == attr
                              and (c := self._constructed(n.child_by_field_name("right")))), None)
        return memo[key]

    def _constructed(self, val: Node | None) -> str | None:
        """`Client(..)` or `pkg.Client(..)` of a class the repo defines (here, or imported from a file of the repo):
        the class name. A library's client (`httpx.Client()`) is not one."""
        fn = val.child_by_field_name("function") if val is not None and val.type == "call" else None
        head, _, last = text(fn, self.src).rpartition(".") if fn is not None else ("", "", "")
        if not last[:1].isupper():
            return None
        if not head and any(s.kind == "class" for s in self.symbols_by_name.get(last, ())):
            return last
        spec, orig = self.imports.get(head.split(".")[0] if head else last) or (None, None)
        if spec is None or self.resolve_import(spec) is None:
            return None
        return orig if not head and orig else last


def compose_wrapped_calls(out: HttpResult) -> None:
    compose_calls(out, WRAPPER, BASES)


def _owner_class(fn: Node | None) -> Node | None:
    """The class whose body declares the method `fn` directly."""
    p = fn.parent if fn is not None else None
    p = p.parent if p is not None and p.type == "decorated_definition" else p
    cls = p.parent if p is not None and p.type == "block" else None
    return cls if cls is not None and cls.type == "class_definition" else None


def _at_module_level(fn: Node) -> bool:
    p = fn.parent
    p = p.parent if p is not None and p.type == "decorated_definition" else p
    return p is not None and p.type == "module"
