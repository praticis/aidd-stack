"""Go's type facts of one file, as the file writes them: its structs' fields and embedded types, its interfaces, the
methods it declares on each receiver, its functions' declared results and its import aliases. They hold no tree node,
so they travel; the resolver and the HTTP scanner read them across files."""

from __future__ import annotations

import re
from typing import Any, NamedTuple

from tree_sitter import Node

from ..base import node_text, walk

TYPE_NODES = ("type_identifier", "qualified_type", "pointer_type", "generic_type")


class GoStruct(NamedTuple):
    fields: dict[str, str]          # name → its type as written ("" for a type parameter); embedded, under its name
    embeds: tuple[str, ...]         # the embedded types, whose fields and methods are promoted


class GoInterface(NamedTuple):
    methods: tuple[str, ...]
    embeds: tuple[str, ...] | None  # None for a type constraint (a union): its methods are unknown


class GoTypes(NamedTuple):
    structs: dict[str, GoStruct]
    interfaces: dict[str, GoInterface]
    methods: dict[str, tuple[str, ...]]     # receiver type → the methods this file declares on it
    funcs: dict[str, tuple[str, ...]]       # function → its declared results, "" for one whose type is not a name
                                            # or is a type parameter
    imports: dict[str, str]                 # alias → import path
    results: dict[str, tuple[str, ...]]     # `Type.method` → its declared results, as `funcs` writes them (none for
                                            # a method that declares none); an interface's methods too

    @classmethod
    def of(cls, facts: Any) -> GoTypes:
        """A file's facts as Go's: none for a file of another language, or one that did not parse."""
        return facts if isinstance(facts, GoTypes) else NONE


NONE = GoTypes({}, {}, {}, {}, {}, {})


def type_text(node: Node | None, src: bytes) -> str | None:
    """`*pkg.T`, `[]T`, `pkg.T` → `pkg.T` / `T`; None for func/map/chan/interface literals."""
    n = node
    while n is not None and n.type in ("pointer_type", "slice_type", "array_type", "parenthesized_type"):
        n = next((c for c in n.children if c.is_named), None)
    if n is None or n.type not in ("type_identifier", "qualified_type", "generic_type"):
        return None
    if n.type == "generic_type":
        n = next((c for c in n.children if c.type in ("type_identifier", "qualified_type")), None)
        if n is None:
            return None
    return node_text(n, src)


def type_parameters(n: Node, src: bytes) -> frozenset[str]:
    """The type parameters a generic function or type declares (`[T any]`), or a method's receiver names
    (`(b *Box[T])`). A type parameter declares no type: a value of one has the type its caller gives it."""
    tp = n.child_by_field_name("type_parameters")
    if tp is not None:
        return frozenset(node_text(nm, src) for d in tp.children if d.type == "type_parameter_declaration"
                         for nm in d.children_by_field_name("name"))
    recv = n.child_by_field_name("receiver")
    args = next((c for c in walk(recv) if c.type == "type_arguments"), None) if recv is not None else None
    return frozenset(node_text(t, src) for e in args.children if e.type == "type_elem" for t in e.children
                     if t.type == "type_identifier") if args is not None else frozenset()


def receiver_type(node: Node, src: bytes) -> str | None:
    recv = node.child_by_field_name("receiver")
    if recv is None:
        return None
    for tid in walk(recv):
        if tid.type == "type_identifier":
            return node_text(tid, src)
    return None


def import_aliases(stmt: Node, spec: str, src: bytes) -> list[str]:
    alias = stmt.child_by_field_name("name")
    if alias is not None:
        return [node_text(alias, src)]
    base = spec.rstrip("/").split("/")[-1]
    base = re.sub(r"^v\d+$", "", base) or spec.rstrip("/").split("/")[-2]
    return [re.sub(r"[-.].*$", "", base) or base]


def type_facts(root: Node, src: bytes) -> GoTypes:
    """The facts of the file whose tree is `root`. A name declared twice (by types local to two functions) keeps its
    last declaration; a struct, the embedded types of the last declaration that has some."""
    structs: dict[str, dict[str, str]] = {}
    embeds: dict[str, tuple[str, ...]] = {}
    interfaces: dict[str, GoInterface] = {}
    methods: dict[str, list[str]] = {}
    funcs: dict[str, tuple[str, ...]] = {}
    imports: dict[str, str] = {}
    results: dict[str, tuple[str, ...]] = {}
    for n in walk(root):
        if n.type == "type_spec":
            _type_spec(n, src, structs, embeds, interfaces, results)
        elif n.type == "method_declaration":
            recv, name = receiver_type(n, src), n.child_by_field_name("name")
            if recv and name is not None:
                methods.setdefault(recv, []).append(node_text(name, src))
                results[f"{recv}.{node_text(name, src)}"] = _declared(n, src, type_parameters(n, src))
        elif n.type == "function_declaration":
            funcs.update(_results(n, src))
        elif n.type == "import_spec" and (path := n.child_by_field_name("path")) is not None:
            spec = node_text(path, src).strip('"`')
            imports.update(dict.fromkeys(import_aliases(n, spec, src), spec))
    return GoTypes({name: GoStruct(fields, embeds.get(name, ())) for name, fields in structs.items()}, interfaces,
                   {recv: tuple(names) for recv, names in methods.items()}, funcs, imports, results)


def _type_spec(n: Node, src: bytes, structs: dict[str, dict[str, str]], embeds: dict[str, tuple[str, ...]],
               interfaces: dict[str, GoInterface], results: dict[str, tuple[str, ...]]) -> None:
    name, typ = n.child_by_field_name("name"), n.child_by_field_name("type")
    if name is None or typ is None:
        return
    if typ.type == "struct_type":
        fields, embedded = _struct(typ, src, type_parameters(n, src))
        structs[node_text(name, src)] = fields
        if embedded:
            embeds[node_text(name, src)] = embedded
    elif typ.type == "interface_type":
        interfaces[node_text(name, src)] = _interface(typ, src)
        params = type_parameters(n, src)
        for el in (c for c in typ.children if c.type == "method_elem"):
            if (nm := el.child_by_field_name("name")) is not None:
                results[f"{node_text(name, src)}.{node_text(nm, src)}"] = _declared(el, src, params)


def _struct(typ: Node, src: bytes, params: frozenset[str]) -> tuple[dict[str, str], tuple[str, ...]]:
    """A struct type's fields, its nested struct types' included, and the types it embeds."""
    fields: dict[str, str] = {}
    embedded: list[str] = []
    for fd in walk(typ):
        if fd.type != "field_declaration":
            continue
        tt = type_text(next((c for c in fd.children if c.type in TYPE_NODES or c.type.endswith("_type")), None), src)
        if tt is None:
            continue
        names = [node_text(c, src) for c in fd.children if c.type == "field_identifier"]
        if not names:                                            # embedded: `Config` / `*Config` — fields are promoted
            embedded.append(tt)
            names = [tt.split(".")[-1]]
        for fname in names:
            fields[fname] = "" if tt in params else tt
    return fields, tuple(embedded)


def _interface(typ: Node, src: bytes) -> GoInterface:
    own: list[str] = []
    inner: list[str] | None = []
    for el in typ.children:
        if el.type == "method_elem":
            nm = next((c for c in el.children if c.type == "field_identifier"), None)
            if nm is not None:
                own.append(node_text(nm, src))
        elif el.type == "type_elem":
            parts = [c for c in el.children if c.is_named]
            tt = type_text(parts[0], src) if len(parts) == 1 else None
            inner = None if tt is None or inner is None else inner + [tt]
    return GoInterface(tuple(own), tuple(inner) if inner is not None else None)


def _results(n: Node, src: bytes) -> dict[str, tuple[str, ...]]:
    """The function `n`'s declared results under its name: `(*T, error)`, `(a, b T)` or `*T`; nothing when it declares
    none, or one whose type is not a name."""
    name, result = n.child_by_field_name("name"), n.child_by_field_name("result")
    if name is None or result is None or (result.type != "parameter_list" and not type_text(result, src)):
        return {}
    return {node_text(name, src): _declared(n, src, type_parameters(n, src))}


def _declared(n: Node, src: bytes, params: frozenset[str]) -> tuple[str, ...]:
    """The types the function, method or interface method `n` declares for its results, "" for one whose type is not
    a name or is one of the type parameters `params`."""
    result = n.child_by_field_name("result")
    if result is None:
        return ()
    if result.type != "parameter_list":
        tt = type_text(result, src) or ""
        return ("" if tt in params else tt,)
    rets: list[str] = []
    for pd in result.children:
        if pd.type == "parameter_declaration":
            ty = next((c for c in pd.children if c.type in TYPE_NODES or c.type.endswith("_type")), None)
            tt = type_text(ty, src) or ""
            rets += ["" if tt in params else tt] * max(1, sum(1 for c in pd.children if c.type == "identifier"))
    return tuple(rets)
