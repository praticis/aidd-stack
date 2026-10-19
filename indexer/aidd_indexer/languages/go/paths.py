"""Go's own path expressions, mixed into the Go scanner: `url.URL` (`u.String()`, `url.Parse(..)`, `u.JoinPath(..)`,
a read of `u.Path`) and grpc-gateway's patterns (`runtime.MustPattern`, `runtime.NewPattern`)."""

from __future__ import annotations

from tree_sitter import Node

from ...core.http_nodes import STRING_NODES
from ...core.paths import unquote
from ...tree import node_text as text, walk


class GoPaths:
    """Mixin of the Go scanner: uses its `path_of`, `scopes` and `src`."""

    def _call_path(self, fn: Node | None, fname: str, arg_nodes: list[Node], lenient: bool,
                   _depth: int) -> tuple[bool, str | None, list[Node]]:
        if fn is None or fn.type != "selector_expression":
            return False, None, arg_nodes
        operand = fn.child_by_field_name("operand")
        recv = text(operand, self.src)
        if fname == "String" and not arg_nodes:                            # u.String(): where u points
            return True, self.path_of(operand, lenient, _depth + 1), arg_nodes
        if fname in ("Parse", "ParseRequestURI") and recv == "url" and arg_nodes:
            return True, self.path_of(arg_nodes[0], lenient, _depth + 1), arg_nodes
        if fname == "JoinPath" and recv != "url":                          # u.JoinPath("x"): u's path, then "x"
            arg_nodes = [operand] + arg_nodes
        if recv == "runtime" and fname == "MustPattern" and arg_nodes:
            return True, self.path_of(arg_nodes[0], lenient, _depth + 1), arg_nodes
        if recv == "runtime" and fname == "NewPattern" and len(arg_nodes) >= 3:
            return True, self._gateway_pattern(arg_nodes), arg_nodes
        return False, None, arg_nodes

    def _gateway_pattern(self, args: list[Node]) -> str | None:
        ops = [int(text(c, self.src)) for c in walk(args[1]) if c.type == "int_literal"]
        pool = [unquote(text(c, self.src)) for c in walk(args[2]) if c.type == "interpreted_string_literal"]
        verb = unquote(text(args[3], self.src)) if len(args) > 3 and args[3].type in STRING_NODES else ""
        return grpc_gateway_pattern(ops, pool, verb)

    def _path_of_name(self, n: Node, lenient: bool, _depth: int) -> str | None:
        if n.type == "selector_expression" and text(n, self.src).endswith(".Path"):
            found = self._url_field(n, lenient, _depth)
            if found is not None:
                return found
        return super()._path_of_name(n, lenient, _depth)

    def _url_field(self, n: Node, lenient: bool, _depth: int) -> str | None:
        """`u.Path` read (`path.Join(u.Path, "/userinfo")`, `u.Path += "x"`): its last assignment before here, else the
        path of the URL `u` holds (`url.Parse("https://host/v1")`)."""
        bound, val = self.scopes.binding(n)
        if bound and val is not None:
            return self.path_of(val, lenient, _depth + 1)
        obj = n.child_by_field_name("operand")
        return self.path_of(obj, lenient, _depth + 1) if obj is not None and obj.type == "identifier" else None


def grpc_gateway_pattern(ops: list[int], pool: list[str], verb: str = "") -> str | None:
    """The path a grpc-gateway `runtime.NewPattern(1, ops, pool, verb)` matches: `ops` is a stack program of (opcode,
    operand) pairs — 1 push a segment, 2 push the literal `pool[operand]`, 3 push the rest of the path, 4 join the
    top `operand` items, 5 capture the top as the variable `pool[operand]`, 0 nothing."""
    stack: list[str] = []
    for i in range(0, len(ops) - 1, 2):
        op, arg = ops[i], ops[i + 1]
        if op == 1:
            stack.append("*")
        elif op == 2 and arg < len(pool):
            stack.append(pool[arg])
        elif op == 3:
            stack.append("**")
        elif op == 4 and 0 < arg <= len(stack):
            stack[-arg:] = ["/".join(stack[-arg:])]
        elif op == 5 and stack and arg < len(pool):     # `{name=memos/*}` matches /memos/<x>: the literal stays
            parts, var = stack[-1].split("/"), "{" + pool[arg] + "}"
            stack[-1] = "/".join(var if p in ("*", "**") else p for p in parts) if {"*", "**"} & set(parts) else var
        elif op != 0:
            return None
    return ("/" + "/".join(stack) + (":" + verb if verb else "")) if stack else None


# -- the directory's constants ---------------------------------------------------------------
