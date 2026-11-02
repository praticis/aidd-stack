"""What a module exports by assigning it, as TypeScript binds it. A JS file with no `import` or `export` is a CommonJS
module: its last `module.exports = x` at the top level is the module's own value, an object literal it assigns gives a
name for each property instead, and each `exports.a = x` or `module.exports.a = x` exports `a` beside it. A TS module's
`export = x` is its own value; where `x` is a namespace, the names the namespace's export clauses export are the
module's, and its own value is the class or the function the namespace merges with, if any."""

from __future__ import annotations

from tree_sitter import Node

OWN = "="               # the name a module's own value is exported under, which no name of a module can be
NAMESPACES = frozenset({"internal_module", "module"})
MERGED = frozenset({"class_declaration", "abstract_class_declaration", "function_declaration", "function_signature"})


def assignments(root: Node, js: bool) -> tuple[list[tuple[str, Node]], dict[str, str]]:
    """What a module exports by assigning it: each name with the value it assigns, `OWN` for the module's own value, in
    order; and the names a namespace a TS module assigns exports, each to the module's name it exports."""
    if js:
        commonjs = not any(s.type in ("import_statement", "export_statement") for s in root.named_children)
        return (_commonjs(root) if commonjs else []), {}
    for s in root.named_children:
        if s.type == "export_statement" and s.named_child_count and any(c.type == "=" for c in s.children):
            value = s.named_children[0]
            names = _namespace(root, text(value)) if value.type == "identifier" else None
            merged = names is None or any(n.type in MERGED and text(n.child_by_field_name("name")) == text(value)
                                          for n in _declarations(root))
            return ([(OWN, value)] if merged else []), names or {}
    return [], {}


def _declarations(root: Node):
    """The module's statements, with a `declare`d one and an expression unwrapped."""
    for s in root.named_children:
        yield s.named_children[0] if s.type in ("ambient_declaration", "expression_statement") and s.named_child_count \
            else s


def _commonjs(root: Node) -> list[tuple[str, Node]]:
    out: list[tuple[str, Node]] = []
    for e in _declarations(root):
        if e.type != "assignment_expression" or e.child_by_field_name("right") is None:
            continue
        name, value = _exported(e.child_by_field_name("left")), e.child_by_field_name("right")
        if name == OWN and value.type == "object":
            out += _properties(value)
        elif name is not None:
            out.append((name, value))
    return out


def _namespace(root: Node, name: str) -> dict[str, str] | None:
    """The names the export clauses of the module's namespace `name` export, each to the name it exports there; None
    where the module declares no such namespace."""
    for n in _declarations(root):
        if n.type in NAMESPACES and text(n.child_by_field_name("name")) == name:
            return dict(_clauses(n.child_by_field_name("body")))
    return None


def required(value: Node | None) -> str | None:
    """The module a `require("./m")` names."""
    if value is None or value.type != "call_expression" or text(value.child_by_field_name("function")) != "require":
        return None
    args = value.child_by_field_name("arguments")
    return string(args.named_children[0] if args is not None and args.named_child_count else None)


def required_name(value: Node | None) -> str | None:
    """What a `require` gives as an import's form: `./m:*` for `require("./m")`, `./m:a` for `require("./m").a`."""
    if value is not None and value.type == "member_expression":
        module, prop = required(value.child_by_field_name("object")), value.child_by_field_name("property")
        return f"{module}:{text(prop)}" if module is not None and prop is not None else None
    module = required(value)
    return f"{module}:*" if module is not None else None


def _exported(left: Node | None) -> str | None:
    """`module.exports` is the module's own value; `exports.a` and `module.exports.a` are its name `a`."""
    if left is None or left.type != "member_expression":
        return None
    if _module_exports(left):
        return OWN
    owner, prop = left.child_by_field_name("object"), left.child_by_field_name("property")
    exports = owner is not None and (owner.type == "identifier" and text(owner) == "exports" or _module_exports(owner))
    return text(prop) if exports and prop is not None and prop.type == "property_identifier" else None


def _module_exports(node: Node) -> bool:
    owner, prop = node.child_by_field_name("object"), node.child_by_field_name("property")
    return node.type == "member_expression" and owner is not None and owner.type == "identifier" \
        and text(owner) == "module" and text(prop) == "exports"


def _properties(literal: Node) -> list[tuple[str, Node]]:
    out: list[tuple[str, Node]] = []
    for p in literal.named_children:
        key = p.child_by_field_name("key") if p.type == "pair" else None
        name = text(p) if p.type == "shorthand_property_identifier" else \
            text(key) if key is not None and key.type == "property_identifier" else string(key)
        value = p if p.type == "shorthand_property_identifier" else p.child_by_field_name("value")
        if name and value is not None:
            out.append((name, value))
    return out


def _clauses(body: Node | None) -> list[tuple[str, str]]:
    clauses = [c for s in (body.named_children if body is not None else ()) if s.type == "export_statement"
               for c in s.named_children if c.type == "export_clause"]
    out = []
    for s in (s for c in clauses for s in c.named_children if s.type == "export_specifier"):
        name, alias = text(s.child_by_field_name("name")), s.child_by_field_name("alias")
        out.append((text(alias) if alias is not None else name, name))
    return out


def string(node: Node | None) -> str | None:
    if node is None or node.type != "string":
        return None
    fragment = next((c for c in node.named_children if c.type == "string_fragment"), None)
    return text(fragment) if fragment is not None else ""


def text(node: Node | None) -> str:
    return node.text.decode(errors="replace") if node is not None else ""
