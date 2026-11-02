"""The type of the value a TS or JS method is called on, as `CallInfo.receiver_type` carries it: the type its base
declares, then the members that follow it. The base is a name read through the binding TypeScript's scopes give it
(`scopes.py`), `this`, a `new`, a call or an `as`; a declaration of the file is read here, and what the module's
imports bring is the type index's (`call:f`, `value:x`)."""

from __future__ import annotations

from tree_sitter import Node

from ...core.types import Unknown
from .commonjs import required_name
from .forms import LOCAL_TYPE, METHOD_RESULT, VALUE, WRAPPERS, in_function, of_type, written
from .scope_model import CLASSES, FIELDS, PARAMETERS
from .scopes import TsScopes
from .type_facts import NO_RESULT

JS_PARAMETER = Unknown("a JS parameter, which declares no type")
INFERRED = Unknown("a type the checker infers through a generic")
NO_ANNOTATION = Unknown("a parameter with no annotation")
FUNCTION_THIS = Unknown("a function's own this, which the class around it does not bind")
OUTER_THIS = Unknown("a this outside a class")
OBJECT_THIS = Unknown("the this of an object literal's method")
EXPRESSION_THIS = Unknown("the this of a class expression")
STATIC_THIS = Unknown("a static member's this, the class itself")
UNDECLARED = Unknown("a name the file does not declare")
LOCAL_REQUIRE = Unknown("a module a function requires, which no module's names hold")
CATCH = Unknown("a catch clause's variable")
ARRAY_ELEMENT = Unknown("an element of a destructured array")
NO_VALUE = Unknown("a variable with no type and no value")
FUNCTION = Unknown("a function, not a value of a class")
CLASS_ITSELF = Unknown("a class itself, whose static side the index does not type")
RECEIVER = Unknown("a receiver that is not a name, a member, `this`, a call, a `new` or an `as`")
OTHER = Unknown("a declaration the table does not read")
DEPTH = 8                           # names followed through the file's declarations, at most

Held = tuple[str, tuple[str, ...]] | Unknown
THIS_HOLDERS = frozenset({"method_definition", "class_static_block", *FIELDS})
IMPORTS = frozenset({"import_specifier", "import_clause", "namespace_import", "import_require_clause"})
CALLABLE = frozenset({"function_declaration", "generator_function_declaration", "function_signature", "arrow_function",
                      "function_expression"})


def receiver_of(receiver: Node, scopes: TsScopes, js: bool = False) -> Held:
    """(the type `receiver`'s base declares, the members that follow it), or why it has none. `js`: a JS file, whose
    parameters declare no type."""
    members, node = [], _unwrapped(receiver)
    while node.type == "member_expression":
        prop = node.child_by_field_name("property")
        if prop is None or prop.type != "property_identifier":
            return RECEIVER
        members.append(_text(prop))
        node = _unwrapped(node.child_by_field_name("object"))
    found = this_class(node, scopes) if node.type == "this" else _value(node, scopes, js, 0)
    return found if isinstance(found, Unknown) else (found[0], found[1] + tuple(reversed(members)))


def this_owner(this: Node, scopes: TsScopes) -> Node | Unknown:
    """The class whose members a `this` reaches, an instance's or the class's own: the one around the method, the field
    or the static block that binds it."""
    binder = scopes.this_of(this)
    if binder is None or binder.type in ("program", "internal_module", "module", "enum_declaration"):
        return OUTER_THIS
    if binder.type not in THIS_HOLDERS:
        return FUNCTION_THIS
    body = binder.parent
    return body.parent if body is not None and body.type == "class_body" else OBJECT_THIS


def this_class(this: Node, scopes: TsScopes) -> Held:
    """The class whose instance a `this` is."""
    holder = this_owner(this, scopes)
    if isinstance(holder, Unknown):
        return holder
    binder = scopes.this_of(this)
    if holder.type == "class":
        return EXPRESSION_THIS
    if binder.type == "class_static_block" or any(c.type == "static" for c in binder.children):
        return STATIC_THIS
    return LOCAL_TYPE if in_function(holder) else (_text(holder.child_by_field_name("name")), ())


def _value(node: Node, scopes: TsScopes, js: bool, depth: int) -> Held:
    node = _unwrapped(node)
    if depth > DEPTH:
        return VALUE
    if node.type == "identifier":
        return _held(node, scopes, js, depth)
    if node.type == "as_expression":
        return _typed(of_type(node.named_children[-1], _bound(scopes)))
    if node.type == "new_expression":
        return _typed(_class_named(node.child_by_field_name("constructor"), scopes))
    if node.type == "call_expression":
        return _called(node.child_by_field_name("function"), scopes)
    return RECEIVER if depth == 0 else VALUE


def _held(name: Node, scopes: TsScopes, js: bool, depth: int) -> Held:
    """The type of the value a name holds, as its declaration in the file says."""
    decls = scopes.binding(name)
    if not decls:
        return UNDECLARED
    decl = decls[0]
    holder = decl.parent
    if holder.type == "variable_declarator" and holder.child_by_field_name("name") == decl:
        return _declarator(holder, scopes, js, depth)
    if holder.type in PARAMETERS or holder.type in ("formal_parameters", "arrow_function"):
        return _parameter(holder, decl, scopes, js)
    if holder.type in IMPORTS:
        return f"value:{_text(name)}", ()
    if holder.type in ("object_pattern", "pair_pattern", "object_assignment_pattern"):
        return _destructured(decl, scopes, js, depth)
    return _declared(holder)


def _declared(holder: Node) -> Unknown:
    if holder.type == "for_in_statement":
        return INFERRED
    if holder.type == "catch_clause":
        return CATCH
    if holder.type in ("array_pattern", "rest_pattern"):
        return ARRAY_ELEMENT
    if holder.type in ("function_declaration", "generator_function_declaration", "function_signature"):
        return FUNCTION
    return CLASS_ITSELF if holder.type in CLASSES else OTHER


def _declarator(declarator: Node, scopes: TsScopes, js: bool, depth: int) -> Held:
    annotation = declarator.child_by_field_name("type")
    if annotation is not None:
        return _typed(of_type(annotation, _bound(scopes)))
    value = declarator.child_by_field_name("value")
    if value is None:
        return NO_VALUE
    if value.type in ("arrow_function", "function_expression"):
        return FUNCTION
    if _required(value):
        return _required_name(declarator.child_by_field_name("name"), declarator)
    return _value(value, scopes, js, depth + 1)


def _parameter(holder: Node, decl: Node, scopes: TsScopes, js: bool) -> Held:
    annotation = holder.child_by_field_name("type") if holder.type in PARAMETERS else None
    if annotation is not None:
        return _typed(of_type(annotation, _bound(scopes)))
    function = holder.parent if holder.type in PARAMETERS else holder
    function = function.parent if function.type == "formal_parameters" else function
    if function.parent is not None and function.parent.type == "arguments":
        return INFERRED
    return JS_PARAMETER if js else NO_ANNOTATION


def _destructured(decl: Node, scopes: TsScopes, js: bool, depth: int) -> Held:
    """`{ x }: Props` or `const { x } = props`: the member `x` of the value the pattern takes apart."""
    pair = decl.parent.type == "pair_pattern"
    key = decl.parent.child_by_field_name("key") if pair else decl
    holder = (decl.parent.parent if pair else decl.parent).parent
    if key is None or key.type not in ("property_identifier", "shorthand_property_identifier_pattern"):
        return OTHER
    if holder is not None and holder.type in PARAMETERS:
        annotation = holder.child_by_field_name("type")
        return _member(annotation, _text(key), scopes) if annotation is not None \
            else _parameter(holder, decl, scopes, js)
    value = holder.child_by_field_name("value") if holder is not None and holder.type == "variable_declarator" else None
    if value is not None and _required(value):
        return _required_name(decl, holder)
    found = _value(value, scopes, js, depth + 1) if value is not None else OTHER
    return found if isinstance(found, Unknown) else (found[0], found[1] + (_text(key),))


def _member(annotation: Node, key: str, scopes: TsScopes) -> Held:
    """A member of an annotated value: of an object type written there, or of the type it names."""
    body = annotation.named_children[-1] if annotation.named_child_count else None
    if body is not None and body.type == "object_type":
        for m in body.named_children:
            name = m.child_by_field_name("name")
            if m.type == "property_signature" and name is not None and _text(name) == key:
                return _typed(of_type(m.child_by_field_name("type"), _bound(scopes)))
        return OTHER
    found = of_type(annotation, _bound(scopes))
    return found if isinstance(found, Unknown) else (found, (key,))


def _class_named(node: Node | None, scopes: TsScopes) -> str | Unknown:
    """The class a `new` names: one a function declares is no class of the module."""
    if node is not None and node.type == "identifier":
        decls = scopes.binding(node)
        if decls and in_function(decls[0]):
            return LOCAL_TYPE
    return written(node)


def _called(function: Node | None, scopes: TsScopes) -> Held:
    """What a call of a function returns: as a function of the file declares it, or as the index reads an import's."""
    found = written(function)
    if isinstance(found, Unknown):
        return METHOD_RESULT
    decls = scopes.binding(function if function.type == "identifier" else function.child_by_field_name("object"))
    holder = decls[0].parent if decls else None
    if holder is None:
        return UNDECLARED
    if holder.type in IMPORTS:
        return f"call:{found}", ()
    if function.type != "identifier":
        return METHOD_RESULT
    declared = holder.child_by_field_name("value") if holder.type == "variable_declarator" else holder
    if declared is None or declared.type not in CALLABLE:
        return OTHER
    result = declared.child_by_field_name("return_type")
    return _typed(of_type(result, _bound(scopes)) if result is not None else NO_RESULT)


def _required(value: Node) -> bool:
    """A `require("./m")`, or a name of one (`require("./m").a`), which the type index reads from the module's facts."""
    return required_name(value) is not None


def _required_name(name: Node, declarator: Node) -> Held:
    """A name a `require` binds: the module's, which its facts hold for the type index; a function's, which none do."""
    return LOCAL_REQUIRE if in_function(declarator) else (f"value:{_text(name)}", ())


def _bound(scopes: TsScopes):
    return lambda name: next(iter(scopes.binding(name)), None)


def _typed(found: str | Unknown) -> Held:
    return found if isinstance(found, Unknown) else (found, ())


def _unwrapped(node: Node) -> Node:
    while node.type in WRAPPERS and node.named_child_count:
        node = node.named_children[0]
    return node


def _text(node: Node | None) -> str:
    return node.text.decode(errors="replace") if node is not None else ""
