"""Go facts of a package that the HTTP scanner reads across files (`GoFacts`): the functions whose every `return` is
one of their parameters, and the package variables that hold a list of verbs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from tree_sitter import Node

from ...core.http_expr import VERB_CONST
from ...core.http_nodes import STRING_NODES
from ...core.http_scope import in_function
from ...core.package_facts import AGREE, LAST, PackageFacts, joined_by
from ...core.paths import HTTP_METHODS, unquote
from ...tree import node_text as text

if TYPE_CHECKING:
    from ...core.http_base import PackageContext

FUNCTIONS = frozenset({"function_declaration", "method_declaration"})


@dataclass
class GoFacts(PackageFacts):
    key: ClassVar[str] = "go"
    passthrough: dict[str, int | None] = joined_by(AGREE)        # function → the parameter every `return` ends with
    verb_lists: dict[str, tuple[str, ...]] = joined_by(LAST)     # `var MethodsPutPost = []string{http.MethodPut, ..}`


def read_package_facts(n: Node, src: bytes, ctx: "PackageContext", path: str) -> bool:
    """A function, or a package variable holding a list of verbs, is read here and holds no constant of the package."""
    if n.type in FUNCTIONS:
        _passthrough(n, src, ctx)
        return True
    return n.type == "var_spec" and _verb_list_var(n, src, ctx)


def _verb_list_var(n: Node, src: bytes, ctx: "PackageContext") -> bool:
    """`var MethodsPutPost = []string{http.MethodPut, http.MethodPost}`, which gin's `Match` may name in another file."""
    name, val = n.child_by_field_name("name"), n.child_by_field_name("value")
    if name is None or val is None or name.type != "identifier" or in_function(n):
        return False
    while val.type == "expression_list" and val.named_child_count == 1:
        val = val.named_children[0]
    verbs = verb_list(val, src) if val.type == "composite_literal" else None
    if verbs:
        GoFacts.of(ctx).put("verb_lists", text(name, src), verbs)
    return verbs is not None


def verb_list(n: Node, src: bytes) -> tuple[str, ...] | None:
    """`[]string{http.MethodPut, "POST"}`: the verbs, when every element is one."""
    body = n.child_by_field_name("body")
    elems = [e.named_children[0] if e.type in ("literal_element", "element") and e.named_child_count else e
             for e in (body.named_children if body is not None else ())]
    out = []
    for e in elems:
        m = VERB_CONST.match(text(e, src))
        v = (m.group(1) or m.group(2) or "").upper() if m else unquote(text(e, src)).upper() if e.type in STRING_NODES else ""
        if v not in HTTP_METHODS:
            return None
        out.append(v)
    return tuple(out) or None


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
        GoFacts.of(ctx).put("passthrough", text(name, src), index)


def passthrough_index(scan, fn: Node) -> int | None:
    """The parameter a function of the repo returns (`_passthrough`): `F` of this package, `pkg.F` of an imported one,
    a method `x.M` by its name when the repo has one `M` of that kind."""
    src, ctx = scan.src, scan.ctx
    if fn.type == "identifier":
        return GoFacts.read(ctx).passthrough.get(text(fn, src))
    if fn.type != "selector_expression":
        return None
    operand, field = fn.child_by_field_name("operand"), text(fn.child_by_field_name("field"), src)
    view, imports = ctx.view, getattr(scan, "imports", {})
    if operand is not None and operand.type == "identifier" and text(operand, src) in imports:
        target = scan.resolve_import(imports[text(operand, src)][0]) if view is not None else None
        there = view.contexts.get(target) if target is not None else None
        return GoFacts.read(there).passthrough.get(field) if there is not None else None
    if view is None:
        return None
    found = {GoFacts.read(c).passthrough[field] for c in view.defining(GoFacts, "passthrough", field)}
    return found.pop() if len(found) == 1 else None
