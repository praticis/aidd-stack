"""What each declaration of a TS or JS file binds, in which scope and in which of TypeScript's meanings, and where each
name read is looked up, as TypeScript's binder builds the scopes and its checker walks them. A `var`, a function
declaration outside strict code, a namespace and an import belong to the function, static block, namespace or file
around them; a `let`, a `const`, a class, an enum, an interface, a type alias and a function declaration in strict
code, to the block around them. A function's parameters and type parameters are seen from its signature, what its body
declares from the body only. A decorator is read outside what it decorates. Code is strict in a module, under a "use
strict" prologue and in a class. The scopes each node opens are `scope_enter`'s."""

from __future__ import annotations

from typing import Callable

from tree_sitter import Node

from ..base import walk
from .scope_enter import ENTERS
from .scope_model import (ALL, CLASS, CLASSES, NAMESPACE, NAMESPACE_ONLY, NAMESPACES, PARAMETERS, TYPE, TYPE_PARAM,
                          TYPES, VALUE, VALUES, Ctx, Declared, Frame, Scope, fields, pattern_names, use_strict)

NAMES = frozenset({"identifier", "type_identifier", "shorthand_property_identifier",
                   "shorthand_property_identifier_pattern", "undefined"})
JSX_TAGS = frozenset({"jsx_opening_element", "jsx_closing_element", "jsx_self_closing_element"})


class Builder:
    def __init__(self, root: Node, src: bytes) -> None:
        self.src = src
        self.declared: set[int] = set()     # the names that a declaration binds, or that no scope reads
        self.reads: dict[int, tuple[Node, Frame, str | None]] = {}     # a name read -> where it is looked up, and as
        self.thises: dict[int, tuple[Node, Node]] = {}                  # a `this` -> the node that binds it
        self.globals = Scope(root)          # what a `declare global` block declares
        program = Scope(root)
        ctx = Ctx(Frame(program, "all", None), program, program, _module(root, src) or use_strict(root), root)
        stack = [(c, root, f, ctx) for c, f in reversed(fields(root))]
        while stack:
            node, parent, field_name, ctx = stack.pop()
            stack.extend((c, node, f, x) for c, f, x in reversed(self._visit(node, parent, field_name, ctx)))

    def _visit(self, node: Node, parent: Node, field_name: str | None, ctx: Ctx) -> list[tuple[Node, str | None, Ctx]]:
        if node.type in NAMES and node.text != b"this":
            self._read(node, parent, field_name, ctx)
            return []
        # tree-sitter writes the `this` of a JSX tag (`<this.C />`) as a name
        if node.type in ("this", "identifier") and field_name != "pattern" and parent.type != "type_predicate":
            self.thises[node.id] = (node, ctx.this)
        declare = DECLARES.get(node.type)
        if declare is not None:
            declare(self, node, ctx)
        enter = ENTERS.get(node.type)
        return enter(self, node, parent, ctx) if enter is not None else [(c, f, ctx) for c, f in fields(node)]

    def _read(self, node: Node, parent: Node, field_name: str | None, ctx: Ctx) -> None:
        p = parent.type
        if node.id in self.declared or p == "import_specifier" or p == "jsx_namespace_name" \
                or (p == "export_specifier" and field_name == "alias") or (p in PARAMETERS and field_name == "name") \
                or (p == "nested_type_identifier" and field_name == "name") \
                or (p in JSX_TAGS and field_name == "name" and _intrinsic(node.text)):
            return
        self.reads[node.id] = (node, ctx.frame, _space(node.type, p))

    def bind(self, scope: Scope, name: Node | None, spaces: frozenset[str], kind: str = "") -> None:
        if name is not None:
            scope.bindings.setdefault(name.text.decode(errors="replace"), []).append(Declared(name, spaces, kind))
            self.declared.add(name.id)

    def bind_pattern(self, scope: Scope, pattern: Node | None, kind: str = "") -> None:
        for name in pattern_names(pattern):
            self.bind(scope, name, VALUES, kind)

    def bind_type_parameters(self, scope: Scope, node: Node) -> None:
        params = node.child_by_field_name("type_parameters")
        for p in params.named_children if params is not None else ():
            if p.type == "type_parameter":
                self.bind(scope, p.child_by_field_name("name"), TYPES, TYPE_PARAM)

    # -- what a node declares in the scopes around it ----------------------------------------------------------------

    def _lexical(self, node: Node, ctx: Ctx) -> None:
        for d in node.named_children:
            if d.type == "variable_declarator":
                self.bind_pattern(ctx.block if node.type == "lexical_declaration" else ctx.container,
                                  d.child_by_field_name("name"))

    def _function(self, node: Node, ctx: Ctx) -> None:
        self.bind(ctx.block if ctx.strict else ctx.container, node.child_by_field_name("name"), VALUES)

    def _block_scoped(self, node: Node, ctx: Ctx) -> None:
        spaces = CLASS if node.type in CLASSES else ALL if node.type == "enum_declaration" else TYPES
        self.bind(ctx.block, node.child_by_field_name("name"), spaces)

    def _namespace(self, node: Node, ctx: Ctx) -> None:
        """`namespace N {}`, or `module N {}`; one that declares only types is no value."""
        name = node.child_by_field_name("name")
        if name is not None and name.type == "nested_identifier":
            self.declared.update(n.id for n in walk(name))
            name = next((n for n in walk(name) if n.type == "identifier"), None)
        if name is not None and name.type == "identifier":
            self.bind(ctx.container, name, NAMESPACES if _instantiated(node) else NAMESPACE_ONLY)

    def _import(self, node: Node, ctx: Ctx) -> None:
        for clause in node.named_children:
            if clause.type in ("import_clause", "import_require_clause"):
                for n in _imported(clause):
                    self.bind(ctx.container, n, ALL)

    def _import_alias(self, node: Node, ctx: Ctx) -> None:
        self.bind(ctx.container, next((c for c in node.named_children if c.type == "identifier"), None), ALL)

    def _infer(self, node: Node, ctx: Ctx) -> None:
        name = next((c for c in node.named_children if c.type == "type_identifier"), None)
        self.bind(ctx.infer if ctx.infer is not None else ctx.block, name, TYPES, TYPE_PARAM)

    def _export(self, node: Node, ctx: Ctx) -> None:
        """`export { a } from "./m"` names another module's `a`, which no scope here binds."""
        if node.child_by_field_name("source") is not None:
            self.declared.update(n.id for c in node.named_children if c.type == "export_clause" for n in walk(c))


def _instantiated(namespace: Node) -> bool:
    """Whether a namespace declares a value: anything but an interface, a type alias, an import of a name and a
    namespace that declares none."""
    body = namespace.child_by_field_name("body")
    for s in body.named_children if body is not None else ():
        if s.type == "export_statement":
            s = s.child_by_field_name("declaration") or s
        if s.type == "expression_statement" and s.named_child_count:
            s = s.named_children[0]
        if s.type in ("internal_module", "module"):
            if _instantiated(s):
                return True
        elif s.type not in ("comment", "interface_declaration", "type_alias_declaration", "import_alias"):
            return True
    return False


def _imported(clause: Node) -> list[Node]:
    """The names an import binds: its default, its namespace, and each named import's alias or name."""
    out = []
    for c in clause.named_children:
        if c.type == "identifier":
            out.append(c)
        elif c.type == "namespace_import":
            out += [n for n in c.named_children if n.type == "identifier"]
        elif c.type == "named_imports":
            out += [s.child_by_field_name("alias") or s.child_by_field_name("name") for s in c.named_children
                    if s.type == "import_specifier"]
    return [n for n in out if n is not None]


def _space(node_type: str, parent: str) -> str | None:
    """What a name read here means; None for what a module exports by a local name, which may be any of them."""
    if node_type == "type_identifier":
        return TYPE
    if parent in ("nested_type_identifier", "nested_identifier", "import_alias"):
        return NAMESPACE
    return None if parent in ("export_specifier", "export_statement") else VALUE


def _intrinsic(name: bytes) -> bool:
    """A JSX tag of the platform (`div`, `my-element`), which no scope binds."""
    return name[:1].islower() or b"-" in name


def _module(root: Node, src: bytes) -> bool:
    if any(c.type in ("import_statement", "export_statement") for c in root.named_children):
        return True
    return b"import.meta" in src and any(n.type == "meta_property" and n.text.startswith(b"import") for n in walk(root))


DECLARES: dict[str, Callable[[Builder, Node, Ctx], None]] = {
    "lexical_declaration": Builder._lexical, "variable_declaration": Builder._lexical,
    "function_declaration": Builder._function, "generator_function_declaration": Builder._function,
    "function_signature": Builder._function,
    **dict.fromkeys(("class_declaration", "abstract_class_declaration", "enum_declaration", "interface_declaration",
                     "type_alias_declaration"), Builder._block_scoped),
    "internal_module": Builder._namespace, "module": Builder._namespace, "import_statement": Builder._import,
    "import_alias": Builder._import_alias, "infer_type": Builder._infer, "export_statement": Builder._export,
}
