"""Go facts of a package that the HTTP scanner reads across files: the functions whose every `return` is one of their
parameters (`PackageContext.passthrough`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tree_sitter import Node

from ...tree import node_text as text

if TYPE_CHECKING:
    from ...core.http_base import PackageContext

FUNCTIONS = frozenset({"function_declaration", "method_declaration"})


def read_package_facts(n: Node, src: bytes, ctx: "PackageContext", path: str) -> bool:
    """A function is read here and holds no constant of the package."""
    if n.type not in FUNCTIONS:
        return False
    _passthrough(n, src, ctx)
    return True


def _passthrough(fn: Node, src: bytes, ctx: "PackageContext") -> None:
    """A Go function whose every `return` is one of its parameters, or something `+` it:
    `func (c *Config) BaseUri(res string) string { if c.SiteUrl() == "" { return res }; return c.BasePath() + res }`:
    a call to it is worth that argument (`_path_of_call`), the code's default; what goes before it comes from
    elsewhere, as a base URL does. Known by its name; two of one name with another parameter give nothing."""
    name, params, body = (fn.child_by_field_name(f) for f in ("name", "parameters", "body"))
    if name is None or params is None or body is None:
        return
    pnames = [text(c, src) for d in params.named_children for c in d.children if c.type == "identifier"]
    index, stack, found = None, list(body.children), False
    while stack:
        d = stack.pop()
        if d.type == "func_literal":
            continue
        stack.extend(d.children)
        if d.type != "return_statement":
            continue
        exprs = [c for c in d.named_children]
        e = exprs[0].named_children[0] if len(exprs) == 1 and exprs[0].type == "expression_list" \
            and exprs[0].named_child_count == 1 else exprs[0] if len(exprs) == 1 else None
        while e is not None and e.type == "binary_expression" and text(e.child_by_field_name("operator"), src) == "+":
            e = e.child_by_field_name("right")
        i = pnames.index(text(e, src)) if e is not None and e.type == "identifier" and text(e, src) in pnames else None
        if i is None or index not in (None, i):
            return
        index, found = i, True
    if found:
        nm = text(name, src)
        ctx.passthrough[nm] = index if ctx.passthrough.get(nm, index) == index else None
