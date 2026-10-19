"""Mounts beyond `use` / `route` with a router: sub-routers kept in a list and mounted in a loop (`defaultRoutes.forEach(
(route) => router.use(route.path, route.route))`, `for (const r of devRoutes)`), and a Fastify plugin handed to
`register` by reference (`app.register(fp(serviceApp), { prefix })`), which mounts the router the plugin receives."""

from __future__ import annotations

from tree_sitter import Node

from ...core.http_base import text, unwrap_arg
from ...core.http_nodes import member
from ...core.http_scope import END

LOOP_METHODS = ("forEach", "map")
PLUGIN_WRAPPERS = ("fastify-plugin",)          # fp(plugin): the same plugin, without its own encapsulation


class TsMountForms:
    """Mixin of the TS scanner: uses its `_mount`, `_own_fields` and `_function_unit`."""

    def listed_mount(self, n: Node, name: str, recv_last: str, arg_nodes: list[Node]) -> bool:
        """`router.use(route.path, route.route)` inside a loop over a module array of `{ path, route }` objects: one
        mount per element, with its fields as the arguments. A list built at run time gives none."""
        var = self._item_name(arg_nodes) if name in ("use", "route") else None
        items = self._loop_items(n, var) if var else None
        mounted = False
        for obj in items or ():
            fields = dict(self._own_fields(obj))
            args = [self._field_of(a, var, fields) for a in arg_nodes]
            if all(a is not None for a in args):
                mounted = self._mount(n, name, recv_last, args) or mounted
        return mounted

    def _item_name(self, arg_nodes: list[Node]) -> str | None:
        """The one name whose fields the arguments read (`route` in `route.path, route.route`)."""
        objs = [member(unwrap_arg(a))[0] for a in arg_nodes]
        names = {text(o, self.src) for o in objs if o is not None and o.type == "identifier"}
        return names.pop() if len(names) == 1 else None

    def _field_of(self, a: Node, var: str, fields: dict[str, Node]) -> Node | None:
        obj, prop = member(unwrap_arg(a))
        if obj is None or prop is None or text(obj, self.src) != var:
            return a
        return fields.get(text(prop, self.src))

    def _loop_items(self, n: Node, var: str) -> list[Node] | None:
        """The object literals of the array the loop around `n` binds `var` to, when every element is one."""
        p, arr = n.parent, None
        while p is not None and arr is None:
            arr = self._looped_array(p, var)
            p = p.parent
        val = (self.resolve_local(arr) or self.scopes.assigned_before(self.scopes.root, END, text(arr, self.src))) \
            if arr is not None else None
        items = [c for c in val.named_children if c.type != "comment"] if val is not None and val.type == "array" else []
        return items if items and all(c.type == "object" for c in items) else None

    def _looped_array(self, p: Node, var: str) -> Node | None:
        """The array name of `for (const var of xs)`, or of `xs.forEach((var) => ..)` whose callback is `p`."""
        if p.type == "for_in_statement":
            left, right = p.child_by_field_name("left"), p.child_by_field_name("right")
            of = any(c.type == "of" for c in p.children)
            ok = of and left is not None and text(left, self.src) == var and right is not None
            return right if ok and right.type == "identifier" else None
        if p.type not in ("arrow_function", "function_expression") or self._params(p)[:1] != [var]:
            return None
        call = p.parent.parent if p.parent is not None and p.parent.type == "arguments" else None
        obj, prop = member(call.child_by_field_name("function")) if call is not None else (None, None)
        ok = obj is not None and obj.type == "identifier" and prop is not None and text(prop, self.src) in LOOP_METHODS
        return obj if ok else None

    def plugin_mount(self, n: Node, name: str, recv_last: str, arg_nodes: list[Node]) -> bool:
        """`app.register(serviceApp, { prefix: "/v1" })` with a plugin of the repo: the router the plugin's function
        receives is mounted on `app` under the prefix (an inline plugin is `region_of`'s)."""
        if name != "register" or not arg_nodes or not recv_last:
            return False
        plugin = self._plugin_of(unwrap_arg(arg_nodes[0]))
        unit = self._function_unit(plugin) if plugin is not None else None
        if unit is None:
            return False
        opts = unwrap_arg(arg_nodes[1]) if len(arg_nodes) > 1 else None
        fields = dict(self._own_fields(opts)) if opts is not None and opts.type == "object" else {}
        prefix = self.path_of(fields["prefix"]) or "" if "prefix" in fields else ""
        base = (self.prefix_for(recv_last, n) or "").rstrip("/")
        self.foreign.append((f"param:{unit[0]}:{unit[1]}:0", self.router_key(recv_last, n), base + prefix))
        return True

    def _plugin_of(self, a: Node) -> Node | None:
        """The plugin an argument names: itself, or what `fp(plugin)` wraps."""
        f, args = a.child_by_field_name("function"), a.child_by_field_name("arguments")
        if a.type in ("identifier", "member_expression") or f is not None and text(f, self.src) == "require":
            return a
        spec = (self.imports.get(text(f, self.src)) or (None,))[0] if f is not None and f.type == "identifier" else None
        inner = [unwrap_arg(c) for c in args.named_children] if args is not None and spec in PLUGIN_WRAPPERS else []
        return inner[0] if inner and inner[0].type in ("identifier", "member_expression") else None
