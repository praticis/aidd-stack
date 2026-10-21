"""The type a Go file declares for a local where the code reads it: the declaration in scope at the use, from the
innermost block and function out, as Go scopes names. The resolver's call receivers and the HTTP scanner ask this one
code. A plain assignment never changes a variable's type, so only declarations count."""

from __future__ import annotations

from tree_sitter import Node

from ...tree import NodeCache
from ..base import node_text, walk
from .type_facts import TYPE_NODES, type_parameters, type_text

FUNCTIONS = frozenset({"function_declaration", "method_declaration", "func_literal"})
# the nodes that open a scope: a block, the implicit blocks of if, for, switch and their clauses, and a function
SCOPES = frozenset({"block", "if_statement", "for_statement", "expression_switch_statement", "type_switch_statement",
                    "select_statement", "expression_case", "type_case", "default_case", "communication_case"}) | FUNCTIONS

Span = tuple[int, int]
Declaration = tuple[Span, int, "str | None"]        # (its scope, where it ends, the type it gives)


def receiver_chain(n: Node, src: bytes) -> tuple[Node, tuple[str, ...]] | None:
    """`uc.policy` → (`uc`, ("policy",)): the name a selector chain starts from, and its fields. Anything else (a
    call's result, an index) is not followed."""
    chain: list[str] = []
    while n.type == "selector_expression":
        fld, n = n.child_by_field_name("field"), n.child_by_field_name("operand")
        if fld is None or n is None:
            return None
        chain.insert(0, node_text(fld, src))
    return (n, tuple(chain)) if n.type == "identifier" else None


def declared_type(name: str, use: Node, src: bytes) -> str | None:
    """The type the declaration of `name` in scope at `use` gives it, as written (`pkg.T`), or `call:pkg.New` (with `#i`
    for one of several results) for the result of a call; None when that declaration shows no type."""
    level: dict[Span, int] = {}
    top = None
    n = use.parent
    while n is not None:
        if n.type in SCOPES:
            level.setdefault((n.start_byte, n.end_byte), len(level))
        if n.type in FUNCTIONS:
            top = n
        n = n.parent
    if top is None:
        return None
    best: tuple[int, int, str | None] | None = None
    for scope, end, typ in _DECLARATIONS.get(top, src).get(name, ()):
        depth = level.get(scope)
        if depth is None or end > use.start_byte:
            continue
        if best is None or depth < best[0] or (depth == best[0] and end >= best[1]):
            best = (depth, end, typ)
    return best[2] if best is not None else None


def _declarations(top: Node, src: bytes) -> dict[str, list[Declaration]]:
    """name → each declaration of it inside the function `top`, closures included: receivers, parameters and named
    results, `var`, and `:=`. One whose type is a type parameter of `top` types nothing."""
    out: dict[str, list[Declaration]] = {}
    for d in walk(top):
        if d.type in FUNCTIONS:
            _parameters(d, src, out)
        elif d.type == "short_var_declaration":
            _add(out, _scope(d), d.end_byte, _values(d.child_by_field_name("left"), d.child_by_field_name("right"), src))
        elif d.type == "var_spec":
            _add(out, _scope(d), d.end_byte, _var_types(d, src))
    params = type_parameters(top, src)
    return {name: [(s, e, None if t in params else t) for s, e, t in found] for name, found in out.items()} \
        if params else out


def _parameters(fn: Node, src: bytes, out: dict[str, list[Declaration]]) -> None:
    body = fn.child_by_field_name("body")
    if body is None:
        return
    scope = (body.start_byte, body.end_byte)        # Go scopes a parameter to the body, as the body's own locals
    for pl in (c for c in fn.children if c.type == "parameter_list"):        # receiver, parameters, results
        found = []
        for pd in (c for c in pl.children if c.type == "parameter_declaration"):
            typ = type_text(next((c for c in pd.children if c.type in TYPE_NODES or c.type.endswith("_type")), None), src)
            found += [(node_text(nm, src), typ) for nm in pd.children if nm.type == "identifier"]
        _add(out, scope, pl.end_byte, found)


def _var_types(d: Node, src: bytes) -> list[tuple[str, str | None]]:
    """`var x T` and `var x T = v`: the type written; `var x = v`: as `x := v` would give it."""
    typ = d.child_by_field_name("type")
    if typ is not None:
        return [(node_text(nm, src), type_text(typ, src)) for nm in d.children if nm.type == "identifier"]
    names = [nm for nm in d.children if nm.type == "identifier"]
    return _pairs(names, d.child_by_field_name("value"), src)


def _values(left: Node | None, right: Node | None, src: bytes) -> list[tuple[str, str | None]]:
    if left is None:
        return []
    return _pairs([c for c in left.children if c.is_named], right, src)


def _pairs(lefts: list[Node], right: Node | None, src: bytes) -> list[tuple[str, str | None]]:
    """(name, type) for each name a declaration gives a value: `T{}` / `&T{}`, `call:pkg.New` (with `#i` for one
    result of a call with several), or None for any other value. A call through anything but a name gives nothing."""
    rights = [c for c in right.children if c.is_named] if right is not None else []
    out = []
    for i, lft in enumerate(lefts):
        r = rights[i] if i < len(rights) else rights[0] if len(rights) == 1 and rights[0].type == "call_expression" else None
        if r is not None and r.type == "unary_expression":                     # &T{...}
            r = next((c for c in r.children if c.is_named), r)
        if r is None:
            continue
        if r.type == "composite_literal":
            out.append((node_text(lft, src), type_text(r.child_by_field_name("type"), src)))
        elif r.type != "call_expression":
            out.append((node_text(lft, src), None))
        elif (fn := r.child_by_field_name("function")) is not None and fn.type in ("identifier", "selector_expression"):
            many = f"#{i}" if len(lefts) > 1 and len(rights) == 1 else ""      # `uc, repo := setup(t)`
            out.append((node_text(lft, src), "call:" + node_text(fn, src) + many))
    return out


def _scope(d: Node) -> Span:
    n = d.parent
    while n is not None and n.type not in SCOPES:
        n = n.parent
    return (n.start_byte, n.end_byte) if n is not None else (0, 0)


def _add(out: dict[str, list[Declaration]], scope: Span, end: int, found: list[tuple[str, str | None]]) -> None:
    for name, typ in found:
        known = out.setdefault(name, [])
        # a `:=` that names a variable its own scope already declares only assigns it again: the type stays
        if all(s != scope for s, _, _ in known):
            known.append((scope, end, typ))


_DECLARATIONS = NodeCache(_declarations)
