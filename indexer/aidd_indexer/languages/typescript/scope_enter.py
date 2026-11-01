"""The scope a node of a TS or JS file opens, what it binds there itself, and what each of its children is read and
declared in. Each takes the builder, the node, its parent and what the node is read in, and gives its children with
what each is read in."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tree_sitter import Node

from .scope_model import (BLOCKS, CLASS, CLASSES, FIELDS, FUNCTIONS, PARAM, PARAMETERS, THIS_FUNCTIONS, TYPE_PARAM,
                          TYPES, VALUES, Ctx, Declared, Frame, Scope, fields, use_strict)

if TYPE_CHECKING:
    from .scope_build import Builder

Children = list[tuple[Node, "str | None", Ctx]]


def _function(b: Builder, node: Node, parent: Node, ctx: Ctx) -> Children:
    """Its parameters and type parameters are seen from its signature; its body sees all it binds."""
    scope = Scope(node)
    params = node.child_by_field_name("parameters")
    for p in params.named_children if params is not None else ():
        b.bind_pattern(scope, p, PARAM)
    b.bind(scope, node.child_by_field_name("parameter"), VALUES, PARAM)
    b.bind_type_parameters(scope, node)
    name = node.child_by_field_name("name")
    if node.type in ("function_expression", "generator_function") and name is not None:
        scope.own = Declared(name, VALUES)
        b.declared.add(name.id)
    body = node.child_by_field_name("body")
    inner = ctx._replace(container=scope, block=scope, strict=ctx.strict or use_strict(body),
                         this=node if node.type in THIS_FUNCTIONS else ctx.this, outside=None)
    out: Children = []
    for c, f in fields(node):
        if f == "body":
            out += _body(c, inner._replace(frame=Frame(scope, "all", ctx.frame)))
        elif f in ("parameters", "parameter", "return_type", "type"):
            out.append((c, f, inner._replace(frame=Frame(scope, "signature", ctx.frame), outside=ctx)))
        elif f == "type_parameters":
            out.append((c, f, inner._replace(frame=Frame(scope, "type-parameters", ctx.frame))))
        else:
            out.append((c, f, ctx))
    return out


def _class(b: Builder, node: Node, parent: Node, ctx: Ctx) -> Children:
    """Its type parameters are its own, and a class expression sees its name; its decorators are read outside it."""
    scope = Scope(node)
    b.bind_type_parameters(scope, node)
    name = node.child_by_field_name("name")
    if node.type == "class" and name is not None:
        scope.own = Declared(name, CLASS)
        b.declared.add(name.id)
    inner = ctx._replace(frame=Frame(scope, "all", ctx.frame), strict=True)
    return [(c, f, ctx if f in ("decorator", "name") else inner) for c, f in fields(node)]


def _parameter(b: Builder, node: Node, parent: Node, ctx: Ctx) -> Children:
    """A parameter's decorators are read outside its method."""
    outside = ctx.outside or ctx
    return [(c, f, outside if f == "decorator" else ctx) for c, f in fields(node)]


def _field(b: Builder, node: Node, parent: Node, ctx: Ctx) -> Children:
    """A field binds `this` in its type and its initializer; its name and decorators are read around the class."""
    return [(c, f, ctx if f in ("name", "property", "decorator") else ctx._replace(this=node)) for c, f in fields(node)]


def _block(b: Builder, node: Node, parent: Node, ctx: Ctx) -> Children:
    """A block, a `for`'s head, a `catch` clause or a `switch`'s cases; a `declare global` block declares globals."""
    if node.type == "statement_block" and parent.type == "ambient_declaration":
        inner = ctx._replace(frame=Frame(b.globals, "all", ctx.frame), container=b.globals, block=b.globals)
        return [(c, f, inner) for c, f in fields(node)]
    scope = Scope(node)
    if node.type == "for_in_statement":
        kind = node.child_by_field_name("kind")
        if kind is not None:
            b.bind_pattern(ctx.container if kind.type == "var" else scope, node.child_by_field_name("left"))
    elif node.type == "catch_clause":
        b.bind_pattern(scope, node.child_by_field_name("parameter"))
    inner = ctx._replace(frame=Frame(scope, "all", ctx.frame), block=scope)
    return [(c, f, inner) for c, f in fields(node)]


def _container(b: Builder, node: Node, parent: Node, ctx: Ctx) -> Children:
    """A class's static block, a namespace or an ambient module: it binds `this`, and holds what its body declares."""
    scope = Scope(node)
    body = node.child_by_field_name("body")
    inner = ctx._replace(frame=Frame(scope, "all", ctx.frame), container=scope, block=scope, this=node,
                         strict=ctx.strict or use_strict(body))
    return [x for c, f in fields(node) for x in (_body(c, inner) if f == "body" else [(c, f, ctx)])]


def _enum(b: Builder, node: Node, parent: Node, ctx: Ctx) -> Children:
    """Its members are in scope in their initializers."""
    scope = Scope(node)
    body = node.child_by_field_name("body")
    for c in body.named_children if body is not None else ():
        name = c if c.type == "property_identifier" else c.child_by_field_name("name")
        if name is not None and name.type == "property_identifier":
            b.bind(scope, name, VALUES)
    inner = ctx._replace(frame=Frame(scope, "all", ctx.frame), this=node)
    return [(c, f, ctx if f == "name" else inner) for c, f in fields(node)]


def _generic(b: Builder, node: Node, parent: Node, ctx: Ctx) -> Children:
    """An interface's or a type alias's type parameters are its own."""
    scope = Scope(node)
    b.bind_type_parameters(scope, node)
    inner = ctx._replace(frame=Frame(scope, "all", ctx.frame))
    return [(c, f, ctx if f == "name" else inner) for c, f in fields(node)]


def _conditional(b: Builder, node: Node, parent: Node, ctx: Ctx) -> Children:
    """The `infer` types of its `extends` are its own, seen there and in the type it gives when it holds."""
    scope = Scope(node)
    inner = ctx._replace(frame=Frame(scope, "all", ctx.frame))
    seen = {"right": inner._replace(infer=scope), "consequence": inner}
    return [(c, f, seen.get(f, ctx)) for c, f in fields(node)]


def _index(b: Builder, node: Node, parent: Node, ctx: Ctx) -> Children:
    """A mapped type's key, or an index signature's parameter."""
    scope = Scope(node)
    clause = next((c for c in node.named_children if c.type == "mapped_type_clause"), None)
    if clause is not None:
        b.bind(scope, clause.child_by_field_name("name"), TYPES, TYPE_PARAM)
    b.bind(scope, node.child_by_field_name("name"), VALUES, PARAM)
    inner = ctx._replace(frame=Frame(scope, "all", ctx.frame))
    return [(c, f, inner) for c, f in fields(node)]


def _body(body: Node, ctx: Ctx) -> Children:
    """A body's statements belong to its owner's scope, not to a block of their own."""
    return [(c, f, ctx) for c, f in fields(body)] if body.type == "statement_block" else [(body, "body", ctx)]


ENTERS: dict[str, Callable[[Builder, Node, Node, Ctx], Children]] = {
    **dict.fromkeys(FUNCTIONS, _function), **dict.fromkeys(CLASSES, _class), **dict.fromkeys(BLOCKS, _block),
    **dict.fromkeys(PARAMETERS, _parameter), **dict.fromkeys(FIELDS, _field),
    **dict.fromkeys(("class_static_block", "internal_module", "module"), _container),
    "enum_declaration": _enum, "interface_declaration": _generic, "type_alias_declaration": _generic,
    "conditional_type": _conditional, "index_signature": _index,
}
