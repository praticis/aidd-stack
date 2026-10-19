"""The app's own HTTP client wrappers in TS/JS. A function whose outbound call builds its path around one of its
parameters is a wrapper: `get(url) { return agent.get(`${apiRoot()}${url}`) }` in an exported object, `request(url,
{ method = "GET" })` doing `fetch(url, { method })`, a class's `send(method, path)`. A call that hands it a literal path
is an outbound call (`requests.get("/account")`, `GET(`${base}/user/x`)`); a call that hands it a parameter of its own
function makes that function a wrapper too (`GET = (url) => request(url, { method: "GET" })`). The target is a function
of the file or an import, a method of an object the file or an import exports, or a method of a class of the repo
(`this`, `new Client()`)."""

from __future__ import annotations

from tree_sitter import Node

from ...core.http_base import HttpResult, Pending, text, unwrap_arg, walk
from ...core.http_nodes import CLASS_NODES, FUNCTION_SCOPES, member
from ...core.http_scope import END
from ...core.http_wrappers import FIELDS, PARAM, compose_wrapped_calls, continues_path, param_shape, verb_of
from ...core.paths import has_literal_segment, normalize_path, unquote

WRAPPER = "ts.client-wrapper"      # fact: wrapper key → (path index, before, after, verb, verb index, parameters,
                                   #   the verb's default)
BASES = "ts.class-bases"           # fact: class → its base's name
CLASS_FIELDS = ("public_field_definition", "field_definition")
CLIENT_LIBRARIES = frozenset({"axios", "superagent", "ky", "got", "node-fetch", "ofetch", "undici", "cross-fetch",
                              "isomorphic-fetch", "wretch", "redaxios"})


class TsClientWrappers:
    """Mixin of the TS scanner: publishes wrappers and class bases, and keeps the calls that may go to a wrapper
    pending."""

    def publish_bases(self, cls: Node) -> None:
        name = cls.child_by_field_name("name")
        heritage = next((c for c in cls.named_children if c.type == "class_heritage"), None)
        ext = next((c for c in heritage.named_children if c.type == "extends_clause"), None) if heritage else None
        base = ext.child_by_field_name("value") if ext is not None \
            else heritage.named_children[0] if heritage is not None and heritage.named_child_count else None
        if name is not None and base is not None and base.type in ("identifier", "member_expression"):
            self.out.publish(BASES, text(name, self.src), (text(base, self.src).split(".")[-1],))

    def library_client(self, recv: str) -> bool:
        """`agent` of `import * as agent from 'superagent'`: a receiver that is an HTTP client library."""
        spec, _ = self.imports.get(recv) or (None, None)
        return spec in CLIENT_LIBRARIES

    def publish_wrapper(self, call: Node, method: str | None, arg_nodes: list[Node], continuing: bool = False,
                        fallback: str | None = None, base: str | None = None) -> bool:
        """`call`, an outbound call whose path is built around a parameter of the function around it: that function is
        a client wrapper, with the call's verb (`method`), the parameter or option field it takes the verb from, or
        else `fallback` (`fetch`'s GET); `base`, the base of the client the call is made on, goes before the path. With
        `continuing`, only when the parameter is the rest of the path (`continues_path`): a path that takes a
        parameter as part of one segment (`/users/${id}`) is the call's own."""
        fn = self._function_around(call)
        keys = self._wrapper_keys(fn) if fn is not None else []
        if not keys:
            return False
        params, options = self._signature(fn)
        url, verb_node = self._request_parts(arg_nodes)
        shape = param_shape(self, url, params) if url is not None else None
        if shape is None or continuing and not continues_path(shape):
            return False
        verb, vi, default = self._wrapper_verb(method, verb_node, [a for a in arg_nodes if a is not url], params,
                                               options, fallback)
        i, before, after = shape
        before = base.rstrip("/") + "/" + before.lstrip("/") if base and before[:1] in ("", "/") else before
        data = (i, before, after, verb.upper() if verb else None, vi, tuple(params), default)
        for key in keys:
            self.out.publish(WRAPPER, key, data)
        return True

    def _wrapper_verb(self, method: str | None, verb_node: Node | None, rest: list[Node], params: list[str],
                      options: dict, fallback: str | None) -> tuple[str | None, int | tuple | None, str | None]:
        """(verb, where it comes from, its default): the `method` option as written or from a parameter, the call's
        own verb, or the `method` of the options a parameter hands on (`fetch(url, options)`, `{ ...options }`)."""
        if verb_node is not None:
            given = verb_of(unquote(text(verb_node, self.src))) if verb_node.type == "string" else None
            vi, default = (None, None) if given else self._verb_param(text(verb_node, self.src), params, options)
            return given, vi, default
        if method is not None:
            return method, None, None
        handed = {text(x, self.src) for a in rest for x in walk(unwrap_arg(a))
                  if x.type == "identifier" and text(x, self.src) in params}
        if len(handed) == 1:
            return None, (params.index(handed.pop()), "method"), fallback
        return fallback, None, None

    def _request_parts(self, arg_nodes: list[Node]) -> tuple[Node | None, Node | None]:
        """The argument that is the path and the expression that is the verb: `fetch(url, { method })`,
        `agent.get(url)`, `axios.request({ url, method })`."""
        args = [unwrap_arg(a) for a in arg_nodes]
        fields = {k: v for a in args if a.type == "object" for k, v in self._option_fields(a)}
        url = args[0] if args and args[0].type != "object" else fields.get("url")
        return url, fields.get("method")

    def _option_fields(self, obj: Node) -> list[tuple[str, Node]]:
        """(key, value) of an object literal's own fields, a shorthand `{ method }` with the name as its value."""
        out = []
        for d in obj.named_children:
            if d.type == "shorthand_property_identifier":
                out.append((text(d, self.src), d))
            elif d.type == "pair" and d.child_by_field_name("key") is not None and d.child_by_field_name("value") is not None:
                out.append((unquote(text(d.child_by_field_name("key"), self.src)), d.child_by_field_name("value")))
        return out

    def _verb_param(self, name: str, params: list[str], options: dict) -> tuple[int | tuple | None, str | None]:
        """Where a verb named `name` comes from: a parameter, or a field of an option parameter (`{ method = "GET" }`),
        with the default it has."""
        if name in options:
            i, key, default = options[name]
            verb = verb_of(unquote(text(default, self.src))) if default is not None and default.type == "string" else None
            return ((i, key) if key else i), verb
        return (params.index(name), None) if name in params else (None, None)

    def _signature(self, fn: Node) -> tuple[list[str], dict[str, tuple[int, str | None, Node | None]]]:
        """`fn`'s parameter names in order ("" for a destructured one), and what a name the body can use comes from:
        (parameter, its key in a destructured one or None, its default)."""
        ps = fn.child_by_field_name("parameters")
        one = fn.child_by_field_name("parameter")                       # x => ...
        items = [c for c in ps.named_children if c.type != "comment"] if ps is not None else [one] if one else []
        names: list[str] = []
        options: dict[str, tuple[int, str | None, Node | None]] = {}
        for i, d in enumerate(items):
            pat, default = _param_parts(d)
            names.append(text(pat, self.src) if pat.type == "identifier" else "")
            if pat.type == "identifier" and default is not None:
                options[names[-1]] = (i, None, default)
            for key, local, dflt in self._pattern_fields(pat) if pat.type == "object_pattern" else ():
                options[local] = (i, key, dflt)
        return names, options

    def _pattern_fields(self, pat: Node) -> list[tuple[str, str, Node | None]]:
        """(key, local name, default) of `{ method = "GET", data, type: kind }`."""
        out = []
        for c in pat.named_children:
            if c.type == "shorthand_property_identifier_pattern":
                out.append((text(c, self.src), text(c, self.src), None))
            elif c.type == "object_assignment_pattern" and c.child_by_field_name("left") is not None:
                name = text(c.child_by_field_name("left"), self.src)
                out.append((name, name, c.child_by_field_name("right")))
            elif c.type == "pair_pattern" and c.child_by_field_name("key") is not None:
                local, default = _param_parts(c.child_by_field_name("value"))
                if local.type == "identifier":
                    out.append((unquote(text(c.child_by_field_name("key"), self.src)), text(local, self.src), default))
        return out

    def _function_around(self, at: Node) -> Node | None:
        p = at.parent
        while p is not None and p.type not in FUNCTION_SCOPES:
            p = p.parent
        return p

    def _wrapper_keys(self, fn: Node) -> list[str]:
        """The names a call reaches `fn` by: `Class.method` for a class's, `<file>:obj.method` for a method of an
        object the module binds or exports (`export default { get(url) {..} }`), `<file>:name` for a function of the
        module, each also under the names the file exports it as."""
        p, path = fn.parent, self.fx.file.path
        holder = p if fn.type == "method_definition" else p.parent if p is not None and (
            p.type == "pair" or p.type in CLASS_FIELDS) else None
        if holder is not None:
            key = p if fn.type != "method_definition" else fn
            name = key.child_by_field_name("name") or key.child_by_field_name("key") or key.child_by_field_name("property")
            if name is None:
                return []
            method = unquote(text(name, self.src))
            if holder.type == "class_body" and holder.parent is not None and holder.parent.child_by_field_name("name"):
                return [f"{text(holder.parent.child_by_field_name('name'), self.src)}.{method}"]
            owner = self._owner(holder) if holder.type == "object" else None
            return [f"{path}:{o}.{method}" for o in self._exported_names(owner)] if owner else []
        name = self._fn_name(fn) if _at_module_level(fn) else None
        return [f"{path}:{n}" for n in self._exported_names(name)] if name else []

    def _exported_names(self, local: str) -> list[str]:
        memo = self.__dict__.setdefault("_export_aliases", None)
        if memo is None:
            memo = self.__dict__["_export_aliases"] = self._exports()[0]
        return [local] + [exported for name, exported in memo if name == local and exported != local]

    # -- the calls that may hand a wrapper its path ---------------------------------------------------------------
    def wrapped_call(self, n: Node, fn: Node, arg_nodes: list[Node]) -> None:
        """A call to a function, object or class of the repo with an argument that can be a path waits for `compose`,
        which knows every wrapper of the repo."""
        target = self._target(fn, n)
        if target is None:
            return
        outer = self._function_around(n)
        keys = self._wrapper_keys(outer) if outer is not None else []
        params = self._signature(outer)[0] if keys else []
        values = tuple(self._value(unwrap_arg(a), params) for a in arg_nodes)
        if any(values):
            item = self.call_info(n, None, "", text(fn, self.src))
            self.out.pending.append(Pending(item, WRAPPER, (target, values, (), keys[0] if keys else None, tuple(params))))

    def _value(self, a: Node, params: list[str]) -> str | tuple | None:
        """A verb, a literal path, the caller's parameter it is built around, or an object's fields."""
        if a.type == "string" and verb_of(unquote(text(a, self.src))):
            return unquote(text(a, self.src)).upper()
        if a.type == "object":
            pairs = tuple((k, v) for k, node in self._option_fields(a) if (v := self._value(node, params)) is not None)
            return (FIELDS, pairs) if pairs else None
        if a.type == "shorthand_property_identifier":
            return (PARAM, params.index(text(a, self.src)), "", "") if text(a, self.src) in params else None
        p = self.path_of(a, lenient=True)
        if p is not None and has_literal_segment(normalize_path(p)):
            return p
        shape = param_shape(self, a, params) if params else None
        return (PARAM, *shape) if shape is not None else None

    def _target(self, fn: Node, at: Node) -> tuple | None:
        if fn.type == "identifier":
            return self._function_target(text(fn, self.src))
        obj, prop = member(fn)
        if obj is None or prop is None:
            return None
        method = text(prop, self.src)
        if obj.type == "this":
            cls = self._class_around(at)
            return ("class", cls, method) if cls else None
        if obj.type != "identifier":
            return None
        name = text(obj, self.src)
        spec, orig = self.imports.get(name) or (None, None)
        if spec is not None:
            unit = self.resolve_import(spec)
            return ("func", f"{unit}:{orig}.{method}" if orig else f"{unit}:{method}") if unit else None
        val = self.resolve_local(obj) or self.scopes.assigned_before(self.scopes.root, END, name)
        if val is not None and val.type == "object":
            return ("func", f"{self.fx.file.path}:{name}.{method}")
        cls = self._constructed(val)
        return ("class", cls, method) if cls else None

    def _function_target(self, name: str) -> tuple | None:
        if any(s.kind == "function" for s in self.symbols_by_name.get(name, ())):
            return ("func", f"{self.fx.file.path}:{name}")
        spec, orig = self.imports.get(name) or (None, None)
        unit = self.resolve_import(spec) if spec is not None and orig is not None else None
        return ("func", f"{unit}:{orig}") if unit else None

    def _class_around(self, at: Node) -> str | None:
        p = at.parent
        while p is not None and p.type not in CLASS_NODES:
            p = p.parent
        name = p.child_by_field_name("name") if p is not None else None
        return text(name, self.src) if name is not None else None

    def _constructed(self, val: Node | None) -> str | None:
        """`new Client(..)` of a class the repo defines (here, or imported from a file of the repo): its name. A
        library's client is not one."""
        ctor = val.child_by_field_name("constructor") if val is not None and val.type == "new_expression" else None
        name = text(ctor, self.src) if ctor is not None and ctor.type == "identifier" else ""
        if any(s.kind == "class" for s in self.symbols_by_name.get(name, ())):
            return name
        spec, orig = self.imports.get(name) or (None, None)
        if spec is None or self.resolve_import(spec) is None:
            return None
        return orig if orig and orig != "default" else name


def compose_wrapped_calls_ts(out: HttpResult) -> None:
    """The calls to the repo's wrappers; a call read as an outbound call at the wrapper's own path (`requests.get(..)`
    on a receiver named like a client) gives way to the wrapped one."""
    known = len(out.calls)
    wrapped = {p.item.id for p in compose_wrapped_calls(out, WRAPPER, BASES)}
    out.calls[:known] = [c for c in out.calls[:known] if c.id not in wrapped]


def _param_parts(d: Node) -> tuple[Node, Node | None]:
    """A parameter's pattern and default: TS's `required_parameter`, JS's `x = 1`, or the pattern itself."""
    if d.type in ("required_parameter", "optional_parameter"):
        return d.child_by_field_name("pattern") or d, d.child_by_field_name("value")
    if d.type in ("assignment_pattern", "object_assignment_pattern"):
        return d.child_by_field_name("left") or d, d.child_by_field_name("right")
    return d, None


def _at_module_level(fn: Node) -> bool:
    p = fn.parent
    if p is not None and p.type in ("variable_declarator", "assignment_expression"):
        p = p.parent
    if p is not None and p.type == "expression_statement":
        p = p.parent
    if p is not None and p.type in ("lexical_declaration", "variable_declaration"):
        p = p.parent
    if p is not None and p.type == "export_statement":
        p = p.parent
    return p is not None and p.type == "program"
