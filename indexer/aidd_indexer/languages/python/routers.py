"""What Python's HTTP scanner asks of Python's own scopes and types: the scope a router's name is bound in, as the
resolver reads a name, and the function or method a router is handed to, read from the call's receiver as the resolver
types it."""

from __future__ import annotations

import re

from tree_sitter import Node

from ...core.http_base import text
from ...core.http_scope import Scopes
from ...core.types import TypeRef, Unknown
from .declared import imports_of, instance, owner
from .forms import BOUND_IN_A_FUNCTION, ref
from .forms import path as class_path
from .scopes import PyScopes
from .type_index import PythonTypeIndex, typed


class PyRouterScopes(Scopes):
    """The core's scopes, with the scope that binds a name as Python's compiler has it: a class body does not enclose
    its methods, and `global` and `nonlocal` bind the name in the scope they point to. What an assignment gives a name
    stays the core's. The index is built on the first question: most files register no route."""

    def __init__(self, root: Node, src: bytes) -> None:
        super().__init__(root, src)
        self._python: PyScopes | None = None

    @property
    def python(self) -> PyScopes:
        if self._python is None:
            self._python = PyScopes(self.root, self.src)
        return self._python

    def binding_scope(self, name: str, at: Node) -> int:
        found = self.python.resolve(self.python.scope_of(at), name).scope
        return found.node.id if found is not None and found.kind != "module" else 0


class PyRouters:
    """Python's scanner keys a router, the application included, by the scope Python binds its name in, and follows a
    router into the parameter of the function or method it is handed to."""

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.scopes = PyRouterScopes(self.fx.tree.root_node, self.src)
        self._receivers: dict[tuple[int, str, str], tuple[str, tuple[str, ...]]] | None = None

    def mark_app(self, name: str, at: Node) -> None:
        self.app_vars.add((self.scopes.binding_scope(name, at), name))

    def is_app(self, name: str, at: Node) -> bool:
        return (self.scopes.binding_scope(name, at), name) in self.app_vars

    def callee_class(self, fn: Node, types: PythonTypeIndex) -> TypeRef | None:
        """The class of the repo a call's callee names, where the call binds the name: a module's or a class body's in
        the module's terms, or what a function's import binds. None for a function or an instance."""
        index, file = self.scopes.python, self.fx.file.path
        written = ref(index, fn)
        if isinstance(written, str):
            cls = types.value(written, file)
            return cls if isinstance(cls, TypeRef) and types.value(f"call:{written}", file) == cls else None
        member = imports_of(index, fn) if written == BOUND_IN_A_FUNCTION and fn.type == "identifier" else None
        return types.imported_class(member.written, file) if member is not None and member.kind == "import" else None

    # -- routers other files name: module variables, router parameters, returned routers ----------------------
    def global_of(self, key: tuple[int, str]) -> str | None:
        scope, name = key
        path = self.fx.file.path
        if scope == 0:
            if not re.fullmatch(r"[A-Za-z_]\w*", name):
                return None
            if self.module_binds(name):
                return f"var:{path}:{name}"
            spec, orig = self.imports.get(name) or (None, None)
            target = self.resolve_import(spec) if spec is not None and orig is not None else None
            return f"var:{target}:{orig}" if target is not None and target.endswith(".py") else None
        fn = self.function_of(scope)
        if fn is None or fn.type != "function_definition":
            return None
        i = self._param(fn, name)[0]
        if i is not None:
            unit = self._unit(fn)
            return f"param:{path}:{unit[0]}:{i - unit[1]}" if unit is not None and i >= unit[1] else None
        return f"ret:{path}:{text(fn.child_by_field_name('name'), self.src)}" if self.returns_name(fn, name) else None

    def _unit(self, fn: Node) -> tuple[str, int] | None:
        """The name a call reaches the function `fn` by, and how many of its parameters the call does not pass:
        (`register`, 0) for a function; (`Users.register`, 1) for a method, whose instance is bound, 0 when static."""
        index = self.scopes.python
        scope = next(s for s in index.scopes if s.node.id == fn.id)
        name = text(fn.child_by_field_name("name"), self.src)
        cls = owner(scope)
        found = class_path(index, cls) if cls is not None else None
        if isinstance(found, Unknown):
            return None
        return (f"{found}.{name}", 1 if instance(index, scope) is not None else 0) if found else (name, 0)

    def router_param_type(self, fn: Node, name: str) -> str | None:
        decl = self._param(fn, name)[1] if fn.type == "function_definition" else None
        typ = decl.child_by_field_name("type") if decl is not None else None
        return text(typ, self.src) if typ is not None else "" if decl is not None else None

    def _param(self, fn: Node, name: str) -> tuple[int | None, Node | None]:
        """Position of the positional parameter `name` of `fn`, and its declaration."""
        params = fn.child_by_field_name("parameters")
        i = 0
        for d in params.named_children if params is not None else ():
            if d.type not in ("identifier", "typed_parameter", "default_parameter", "typed_default_parameter"):
                continue
            ident = d if d.type == "identifier" else d.child_by_field_name("name") or \
                next((c for c in d.children if c.type == "identifier"), None)
            if ident is not None and text(ident, self.src) == name:
                return i, d
            i += 1
        return None, None

    def _router_arguments(self, n: Node, fn: Node, args: Node) -> None:
        """`register_routes(app)`, `init_app(app)`: a router handed to a function of this file or an imported one;
        `users.register(v1)`, `routes.register(v1)`: to a method of a typed value, or a function of a module."""
        unit = self._callee(fn) if fn.type == "identifier" else self._typed_callee(n, fn)
        if unit is None:
            return
        pos = [a for a in args.children if a.is_named and a.type != "keyword_argument"]
        for i, a in enumerate(pos):
            if a.type == "identifier":
                self.router_args.append((f"param:{unit[0]}:{unit[1]}:{i}", text(a, self.src), n, ""))

    def _callee(self, fn: Node) -> tuple[str, str] | None:
        fname = text(fn, self.src)
        if any(s.kind == "function" for s in self.symbols_by_name.get(fname, ())):
            return self.fx.file.path, fname
        spec, orig = self.imports.get(fname) or (None, None)
        unit = self.resolve_import(spec) if spec is not None and orig is not None else None
        return (unit, orig) if unit is not None else None

    def _typed_callee(self, call: Node, fn: Node) -> tuple[str, str] | None:
        """The file and the name of the function a call on a receiver reaches."""
        declaring = self.declaring(call, fn)
        if declaring is None:
            return None
        method = text(fn.child_by_field_name("attribute"), self.src)
        return f"{declaring.package}.py", f"{declaring.name}.{method}" if declaring.name else method

    def declaring(self, call: Node, fn: Node) -> TypeRef | None:
        """What declares the function a call on a receiver reaches, from the type the extraction gave the receiver: the
        class that declares the method, up the receiver's MRO, or the module of the function."""
        obj, attr = fn.child_by_field_name("object"), fn.child_by_field_name("attribute")
        view = self.ctx.view
        if obj is None or attr is None or view is None or view.types is None:
            return None
        receiver = self._typed_receivers().get((call.start_point[0] + 1, text(attr, self.src), text(obj, self.src)[:80]))
        types = view.types.of("python")
        found = typed(types, self.fx.file.path, *receiver) if receiver is not None else None
        declaring = types.method(found, text(attr, self.src)) if isinstance(found, TypeRef) else None
        return declaring if isinstance(declaring, TypeRef) else None

    def _typed_receivers(self) -> dict[tuple[int, str, str], tuple[str, tuple[str, ...]]]:
        if self._receivers is None:
            self._receivers = {(c.line, c.callee_name, c.receiver): (c.receiver_type, c.receiver_path)
                               for c in self.fx.calls if c.receiver_type is not None and c.receiver is not None}
        return self._receivers
