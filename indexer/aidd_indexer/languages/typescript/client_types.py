"""The type a receiver declares, for the TS scanner of HTTP: the class of the repo whose wrappers a call reaches, or the
package a client library's type comes from. It asks the index the resolver asks (`receiver_of` and `typed`) and reads
only its answer: a receiver whose type the declarations in sight do not give has none, and the scanner knows it as it
did before types."""

from __future__ import annotations

from tree_sitter import Node

from ...core.http_nodes import member
from ...core.types import TypeRef, Unknown
from .receivers import receiver_of
from .scopes import TsScopes
from .type_index import Outside, Typed, qualified, typed

CLIENT_TYPES = {"axios": frozenset({"Axios", "AxiosInstance", "AxiosStatic"}), "got": frozenset({"Got"}),
                "ky": frozenset({"KyInstance"}), "superagent": frozenset({"SuperAgent", "SuperAgentStatic"}),
                "wretch": frozenset({"Wretch"})}      # the types of those packages a request is made on
CLIENT_LIBRARIES = frozenset({"axios", "superagent", "ky", "got", "node-fetch", "ofetch", "undici", "cross-fetch",
                              "isomorphic-fetch", "wretch", "redaxios"})


def callee_node(call: Node) -> Node | None:
    """The function a call names: for `await api.post<T>(..)` the grammar puts the `await` in the callee."""
    fn = call.child_by_field_name("function")
    return fn.named_children[0] if fn is not None and fn.type == "await_expression" and fn.named_child_count == 1 else fn


class TsClientTypes:
    """Mixin of the TS scanner: what the type index says a receiver is."""
    ts_scopes: TsScopes | None = None          # the file's scope index, built on its first question

    def file_scopes(self) -> TsScopes:
        if self.ts_scopes is None:
            self.ts_scopes = TsScopes(self.fx.tree.root_node, self.src)
        return self.ts_scopes

    def declared_type(self, receiver: Node | None) -> Typed:
        """What the code declares for `receiver`, or `Unknown` with the reason."""
        if receiver is None:
            return Unknown("a call that is no member's")
        held = receiver_of(receiver, self.file_scopes(), self.fx.file.language == "javascript")
        if isinstance(held, Unknown):
            return held
        return typed(self.ctx.view.types.of(self.fx.file.language), self.fx.file.path, *held)

    def typed_target(self, receiver: Node, method: str) -> tuple | None:
        """The wrapper a call of `method` reaches when the receiver is typed as a class of the repo: the one the class
        or the base that declares the method holds, and none where that method is no wrapper (no base is published
        under a qualified name, so the lookup does not go on to the bases of the class that declares it)."""
        found = self.declared_type(receiver)
        if not isinstance(found, TypeRef):
            return None
        owner = self.ctx.view.types.of(self.fx.file.language).method(found, method)
        return ("class", qualified(owner), method) if isinstance(owner, TypeRef) and owner.name else None

    def client_typed(self, call: Node) -> bool:
        """Whether the call's receiver is typed by a type of a client library that a request is made on (`AxiosInstance`)."""
        found = self.declared_type(member(callee_node(call))[0])
        return isinstance(found, Outside) and found.member in CLIENT_TYPES.get(found.name, ())
