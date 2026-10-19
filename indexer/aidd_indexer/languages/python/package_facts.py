"""Python facts of a package that the HTTP scanner reads across files: the project's router classes
(`PackageContext.classes`), with what their `__init__` makes of the prefix."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tree_sitter import Node

from ...core.http_nodes import STRING_NODES, has_interpolation
from ...core.http_scope import in_function
from ...core.paths import unquote
from ...tree import node_text as text, walk

if TYPE_CHECKING:
    from ...core.http_base import PackageContext


def read_package_facts(n: Node, src: bytes, ctx: "PackageContext", path: str) -> bool:
    """A class is read here and holds no constant of the package."""
    if n.type != "class_definition":
        return False
    _py_class(n, src, ctx)
    return True


PREFIX_KEYWORDS = ("prefix", "url_prefix")      # APIRouter's, Blueprint's


def _py_class(n: Node, src: bytes, ctx: "PackageContext") -> None:
    """`class UserAPIRouter(APIRouter)`: its bases' names and what its `__init__` makes of the prefix
    (`_init_prefix`), so that a call to it in another file reads as the router it builds (`PyScanner._router_class`)."""
    name, sup = n.child_by_field_name("name"), n.child_by_field_name("superclasses")
    bases = tuple(text(b, src).split(".")[-1] for b in (sup.named_children if sup is not None else ())
                  if b.type in ("identifier", "attribute"))
    if name is None or not bases or in_function(n):
        return
    cname, info = text(name, src), (bases, _init_prefix(n, src))
    ctx.classes[cname] = info if ctx.classes.get(cname, info) == info else None


def _init_prefix(cls: Node, src: bytes) -> tuple | None:
    """What the class's own `__init__` hands `super().__init__` (or `Base.__init__(self, ..)`) as the prefix:
    ("lit", "/x"); ("param", name, its position after `self` — None when keyword-only —, its literal default): the
    call's argument for it; ("none",) when it hands none, or something not read. None without an `__init__` of its
    own, or with one that passes the caller's keywords on (`**kwargs`) without naming the prefix: the call reads as
    the base's would."""
    body = cls.child_by_field_name("body")
    init = next((f for c in (body.named_children if body is not None else ())
                 for f in [c.child_by_field_name("definition") if c.type == "decorated_definition" else c]
                 if f is not None and f.type == "function_definition"
                 and text(f.child_by_field_name("name"), src) == "__init__"), None)
    call = next((c for c in walk(init) if c.type == "call" and _super_init(c, src)), None) if init is not None else None
    args = call.child_by_field_name("arguments") if call is not None else None
    if args is None:
        return None
    kw = {text(a.child_by_field_name("name"), src): a.child_by_field_name("value")
          for a in args.named_children if a.type == "keyword_argument"}
    v = next((kw[k] for k in PREFIX_KEYWORDS if k in kw), None)
    if v is None:
        return None if any(a.type == "dictionary_splat" for a in args.named_children) else ("none",)
    if v.type in STRING_NODES and not has_interpolation(v):
        return ("lit", unquote(text(v, src)))
    return _init_param(init, text(v, src), src) if v.type == "identifier" else ("none",)


def _super_init(c: Node, src: bytes) -> bool:
    fn = c.child_by_field_name("function")
    attr = fn.child_by_field_name("attribute") if fn is not None and fn.type == "attribute" else None
    obj = fn.child_by_field_name("object") if attr is not None else None
    if obj is None or text(attr, src) != "__init__":
        return False
    return obj.type == "identifier" or obj.type == "call" and text(obj.child_by_field_name("function"), src) == "super"


def _init_param(init: Node, name: str, src: bytes) -> tuple:
    """`name` among `__init__`'s parameters: ("param", name, position after `self` or None, literal default)."""
    params = init.child_by_field_name("parameters")
    i, keyword_only = 0, False
    for d in params.named_children if params is not None else ():
        if d.type in ("list_splat_pattern", "keyword_separator"):
            keyword_only = True
            continue
        if d.type not in ("identifier", "typed_parameter", "default_parameter", "typed_default_parameter"):
            continue
        ident = d if d.type == "identifier" else d.child_by_field_name("name") or \
            next((c for c in d.children if c.type == "identifier"), None)
        if ident is not None and text(ident, src) == name:
            default = d.child_by_field_name("value") if d.type.endswith("default_parameter") else None
            lit = unquote(text(default, src)) if default is not None and default.type in STRING_NODES \
                and not has_interpolation(default) else None
            return ("param", name, None if keyword_only else i - 1, lit)
        i += 1
    return ("none",)                                # a local or a constant: not read
