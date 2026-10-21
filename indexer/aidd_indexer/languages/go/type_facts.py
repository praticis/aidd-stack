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
    fields: dict[str, str]          # name → its type as written; an embedded type under its own name
    embeds: tuple[str, ...]         # the embedded types, whose fields and methods are promoted


class GoInterface(NamedTuple):
    methods: tuple[str, ...]
    embeds: tuple[str, ...] | None  # None for a type constraint (a union): its methods are unknown


class GoTypes(NamedTuple):
    structs: dict[str, GoStruct]
    interfaces: dict[str, GoInterface]
    methods: dict[str, tuple[str, ...]]     # receiver type → the methods this file declares on it
    funcs: dict[str, tuple[str, ...]]       # function → its declared results, "" for one whose type is not a name
    imports: dict[str, str]                 # alias → import path

    @classmethod
    def of(cls, facts: Any) -> GoTypes:
        """A file's facts as Go's: none for a file of another language, or one that did not parse."""
        return facts if isinstance(facts, GoTypes) else NONE

    def field_type(self, struct: str, name: str) -> str | None:
        """The type this file's struct `struct` writes for its field `name`."""
        st = self.structs.get(struct)
        return st.fields.get(name) if st is not None else None


NONE = GoTypes({}, {}, {}, {}, {})


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
    for n in walk(root):
        if n.type == "type_spec":
            _type_spec(n, src, structs, embeds, interfaces)
        elif n.type == "method_declaration":
            recv, name = receiver_type(n, src), n.child_by_field_name("name")
            if recv and name is not None:
                methods.setdefault(recv, []).append(node_text(name, src))
        elif n.type == "function_declaration":
            funcs.update(_results(n, src))
        elif n.type == "import_spec" and (path := n.child_by_field_name("path")) is not None:
            spec = node_text(path, src).strip('"`')
            imports.update(dict.fromkeys(import_aliases(n, spec, src), spec))
    return GoTypes({name: GoStruct(fields, embeds.get(name, ())) for name, fields in structs.items()}, interfaces,
                   {recv: tuple(names) for recv, names in methods.items()}, funcs, imports)


def _type_spec(n: Node, src: bytes, structs: dict[str, dict[str, str]], embeds: dict[str, tuple[str, ...]],
               interfaces: dict[str, GoInterface]) -> None:
    name, typ = n.child_by_field_name("name"), n.child_by_field_name("type")
    if name is None or typ is None:
        return
    if typ.type == "struct_type":
        fields, embedded = _struct(typ, src)
        structs[node_text(name, src)] = fields
        if embedded:
            embeds[node_text(name, src)] = embedded
    elif typ.type == "interface_type":
        interfaces[node_text(name, src)] = _interface(typ, src)


def _struct(typ: Node, src: bytes) -> tuple[dict[str, str], tuple[str, ...]]:
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
            fields[fname] = tt
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
    if name is None or result is None:
        return {}
    if result.type != "parameter_list":
        tt = type_text(result, src)
        return {node_text(name, src): (tt,)} if tt else {}
    rets: list[str] = []
    for pd in result.children:
        if pd.type == "parameter_declaration":
            ty = next((c for c in pd.children if c.type in TYPE_NODES or c.type.endswith("_type")), None)
            rets += [type_text(ty, src) or ""] * max(1, sum(1 for c in pd.children if c.type == "identifier"))
    return {node_text(name, src): tuple(rets)}
