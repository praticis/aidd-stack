"""TS's and JS's type facts of one file: what each name of its module denotes, its classes' and interfaces' bases,
fields and methods, and what it exports, as the file declares them, in the terms of its module (`forms.py`). A class's
fields are its instance's: its fields, its parameter properties and its getters. The facts hold no tree node, so they
travel; the type index reads them across files."""

from __future__ import annotations

from typing import Any, NamedTuple

from tree_sitter import Node

from ...core.types import Unknown
from .forms import NOT_A_REFERENCE, of_type, of_value, written

NO_RESULT = Unknown("a result the function does not declare")
FUNCTIONS = frozenset({"arrow_function", "function_expression", "function", "generator_function"})


class Member(NamedTuple):
    kind: str           # class, interface, alias, function, value, import, enum or namespace
    written: str        # alias and value: the type; function: its declared result; import: the module and its name
                        # there (`./models:B`, `./models:*` for the whole module, `./models:default`)
    why: str = ""       # a value or a function's result with no type: the reason


class Owner(NamedTuple):
    """A class or an interface."""
    extends: tuple[str | Unknown, ...]      # a class's base class; an interface's bases
    implements: tuple[str | Unknown, ...]
    fields: dict[str, Member]
    methods: dict[str, Member]

    @property
    def bases(self) -> tuple[str | Unknown, ...]:
        return self.extends + self.implements


class TsTypes(NamedTuple):
    members: dict[str, Member]
    owners: dict[str, Owner]
    exports: dict[str, str]         # an exported name -> the module's own name; `export default x` under `default`
    reexports: dict[str, str]       # an exported name -> the module and its name there
    stars: tuple[str, ...]          # the modules `export * from` names

    @classmethod
    def of(cls, facts: Any) -> TsTypes:
        """A file's facts as TS's: none for a file of another language."""
        return facts if isinstance(facts, TsTypes) else NONE


NONE = TsTypes({}, {}, {}, {}, ())


def type_facts(root: Node) -> TsTypes:
    facts = TsTypes({}, {}, {}, {}, ())
    stars: list[str] = []
    for statement in root.named_children:
        _statement(facts, stars, statement)
    return facts._replace(stars=tuple(stars))


def _statement(facts: TsTypes, stars: list[str], node: Node) -> None:
    if node.type == "export_statement":
        _export(facts, stars, node)
    elif node.type == "import_statement":
        _import(facts, node)
    elif node.type == "expression_statement" and node.named_child_count:
        _declaration(facts, node.named_children[0])
    else:
        _declaration(facts, node)


def _declaration(facts: TsTypes, node: Node) -> list[str]:
    """What a declaration of the module binds, `declare`d too; its names."""
    if node.type == "ambient_declaration" and node.named_child_count:
        node = node.named_children[0]
    t, name = node.type, node.child_by_field_name("name")
    if t in ("class_declaration", "abstract_class_declaration") and name is not None:
        facts.members[_text(name)] = Member("class", _text(name))
        facts.owners[_text(name)] = _class(node)
    elif t == "interface_declaration" and name is not None:
        facts.members[_text(name)] = Member("interface", _text(name))
        facts.owners[_text(name)] = _interface(node)
    elif t == "type_alias_declaration" and name is not None:
        facts.members[_text(name)] = _member("alias", of_type(node.child_by_field_name("value"), _type_parameter))
    elif t in ("function_declaration", "function_signature", "generator_function_declaration") and name is not None:
        facts.members.setdefault(_text(name), _function(node))
    elif t in ("enum_declaration", "internal_module", "module") and name is not None and name.type == "identifier":
        facts.members[_text(name)] = Member("enum" if t == "enum_declaration" else "namespace", _text(name))
    elif t in ("lexical_declaration", "variable_declaration"):
        return [n for d in node.named_children if d.type == "variable_declarator" for n in _variable(facts, d)]
    else:
        return []
    return [_text(name)]


def _variable(facts: TsTypes, declarator: Node) -> list[str]:
    name, value = declarator.child_by_field_name("name"), declarator.child_by_field_name("value")
    required = _required(value)
    if name is not None and name.type == "object_pattern" and required is not None:
        names = [c.child_by_field_name("value") or c if c.type == "pair_pattern" else c for c in name.named_children]
        for c, n in zip(name.named_children, names):
            remote = c.child_by_field_name("key") if c.type == "pair_pattern" else c
            if n.type in ("identifier", "shorthand_property_identifier_pattern") and remote is not None:
                facts.members[_text(n)] = Member("import", f"{required}:{_text(remote)}")
        return [_text(n) for n in names if n.type in ("identifier", "shorthand_property_identifier_pattern")]
    if name is None or name.type != "identifier":
        return []
    annotation = declarator.child_by_field_name("type")
    if required is not None:
        found = Member("import", f"{required}:*")
    elif annotation is not None:
        found = _member("value", of_type(annotation, _type_parameter))
    elif value is not None and value.type in FUNCTIONS:
        found = _function(value)
    else:
        found = _member("value", of_value(value, _type_parameter))
    facts.members[_text(name)] = found
    return [_text(name)]


def _required(value: Node | None) -> str | None:
    """The module a `require("./m")` names."""
    if value is None or value.type != "call_expression" or _text(value.child_by_field_name("function")) != "require":
        return None
    args = value.child_by_field_name("arguments")
    first = args.named_children[0] if args is not None and args.named_child_count else None
    return _string(first)


def _function(node: Node) -> Member:
    result = node.child_by_field_name("return_type")
    return _member("function", of_type(result, _type_parameter)) if result is not None \
        else Member("function", "", NO_RESULT.reason)


def _class(node: Node) -> Owner:
    extends: list[str | Unknown] = []
    implements: list[str | Unknown] = []
    for heritage in (c for c in node.named_children if c.type == "class_heritage"):
        for clause in heritage.named_children:
            if clause.type == "extends_clause":
                extends.append(written(clause.child_by_field_name("value")))
            elif clause.type == "implements_clause":
                implements += [of_type(t, _type_parameter) for t in clause.named_children]
            else:
                extends.append(written(clause))
    fields: dict[str, Member] = {}
    methods: dict[str, Member] = {}
    body = node.child_by_field_name("body")
    for m in body.named_children if body is not None else ():
        _class_member(m, fields, methods)
    return Owner(tuple(extends), tuple(implements), fields, methods)


def _class_member(m: Node, fields: dict[str, Member], methods: dict[str, Member]) -> None:
    name = m.child_by_field_name("name") or m.child_by_field_name("property")
    if name is None or name.type != "property_identifier" or any(c.type == "static" for c in m.children):
        return
    if m.type in ("public_field_definition", "field_definition"):
        annotation = m.child_by_field_name("type")
        fields[_text(name)] = _member("value", of_type(annotation, _type_parameter) if annotation is not None
                                      else of_value(m.child_by_field_name("value"), _type_parameter))
    elif _text(name) == "constructor":
        fields.update(_parameter_properties(m))
    elif any(c.type == "get" for c in m.children):
        fields[_text(name)] = _member("value", of_type(m.child_by_field_name("return_type"), _type_parameter))
    elif m.type in ("method_definition", "method_signature", "abstract_method_signature"):
        methods.setdefault(_text(name), _function(m))


def _parameter_properties(constructor: Node) -> dict[str, Member]:
    """`constructor(private readonly b: B)`: a field of the instance."""
    params = constructor.child_by_field_name("parameters")
    out = {}
    for p in params.named_children if params is not None else ():
        pattern = p.child_by_field_name("pattern")
        if any(c.type in ("accessibility_modifier", "readonly", "override_modifier") for c in p.children) \
                and pattern is not None and pattern.type == "identifier":
            out[_text(pattern)] = _member("value", of_type(p.child_by_field_name("type"), _type_parameter))
    return out


def _interface(node: Node) -> Owner:
    bases = [of_type(t, _type_parameter) for c in node.named_children if c.type == "extends_type_clause"
             for t in c.named_children]
    fields: dict[str, Member] = {}
    methods: dict[str, Member] = {}
    body = node.child_by_field_name("body")
    for m in body.named_children if body is not None else ():
        name = m.child_by_field_name("name")
        if name is None or name.type != "property_identifier":
            continue
        if m.type == "property_signature":
            fields[_text(name)] = _member("value", of_type(m.child_by_field_name("type"), _type_parameter))
        elif m.type == "method_signature":
            methods.setdefault(_text(name), _function(m))
    return Owner(tuple(bases), (), fields, methods)


def _import(facts: TsTypes, node: Node) -> None:
    for clause in node.named_children:
        if clause.type == "import_require_clause":
            spec = _string(clause.child_by_field_name("source"))
            names = [(c, "*") for c in clause.named_children if c.type == "identifier"]
        elif clause.type == "import_clause":
            spec = _string(node.child_by_field_name("source"))
            names = _imported(clause)
        else:
            continue
        for local, remote in names if spec is not None else ():
            facts.members[_text(local)] = Member("import", f"{spec}:{remote}")


def _imported(clause: Node) -> list[tuple[Node, str]]:
    out: list[tuple[Node, str]] = []
    for c in clause.named_children:
        if c.type == "identifier":
            out.append((c, "default"))
        elif c.type == "namespace_import":
            out += [(n, "*") for n in c.named_children if n.type == "identifier"]
        elif c.type == "named_imports":
            for s in (s for s in c.named_children if s.type == "import_specifier"):
                name = s.child_by_field_name("name")
                out.append((s.child_by_field_name("alias") or name, _text(name)))
    return out


def _export(facts: TsTypes, stars: list[str], node: Node) -> None:
    spec = _string(node.child_by_field_name("source"))
    declaration = node.child_by_field_name("declaration")
    value = node.child_by_field_name("value")
    default = any(c.type == "default" for c in node.children)
    if declaration is not None:
        names = _declaration(facts, declaration)
        facts.exports.update({"default" if default else n: n for n in names[:1 if default else None]})
    elif default and value is not None and value.type == "identifier":
        facts.exports["default"] = _text(value)
    elif spec is not None and not any(c.type == "export_clause" for c in node.named_children):
        _star(facts, stars, node, spec)
    for clause in (c for c in node.named_children if c.type == "export_clause"):
        for s in (s for s in clause.named_children if s.type == "export_specifier"):
            name = _text(s.child_by_field_name("name"))
            alias = s.child_by_field_name("alias")
            exported = _text(alias) if alias is not None else name
            if spec is not None:
                facts.reexports[exported] = f"{spec}:{name}"
            else:
                facts.exports[exported] = name


def _star(facts: TsTypes, stars: list[str], node: Node, spec: str) -> None:
    """`export * from "./m"`, or `export * as ns from "./m"`."""
    namespace = next((c for c in node.named_children if c.type == "namespace_export"), None)
    name = next((n for n in namespace.named_children if n.type == "identifier"), None) if namespace else None
    if name is not None:
        facts.reexports[_text(name)] = f"{spec}:*"
    elif namespace is None:
        stars.append(spec)


def _type_parameter(name: Node) -> Node | None:
    """The type parameter of a declaration around it that a type name names: what the module's names cannot shadow."""
    p = name.parent
    while p is not None and p.type != "program":
        params = p.child_by_field_name("type_parameters")
        for tp in params.named_children if params is not None else ():
            n = tp.child_by_field_name("name") if tp.type == "type_parameter" else None
            if n is not None and n.text == name.text:
                return n
        p = p.parent
    return None


def _member(kind: str, form: str | Unknown) -> Member:
    return Member(kind, "", form.reason) if isinstance(form, Unknown) else Member(kind, form)


def _string(node: Node | None) -> str | None:
    if node is None or node.type != "string":
        return None
    fragment = next((c for c in node.named_children if c.type == "string_fragment"), None)
    return _text(fragment) if fragment is not None else ""


def _text(node: Node | None) -> str:
    return node.text.decode(errors="replace") if node is not None else ""


__all__ = ["Member", "NOT_A_REFERENCE", "NO_RESULT", "Owner", "TsTypes", "type_facts"]
