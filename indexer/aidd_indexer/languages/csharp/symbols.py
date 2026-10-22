"""C# support: namespaces (block and file-scoped) prefix qualified names; `using X;` resolves to the
module that declares namespace X, otherwise to a NuGet package (System.* / Microsoft.* = framework).
Static receiver types for method calls (`this._query.FindByIdAsync()` → `IAccountQuery.FindByIdAsync`)
and interface → unique implementer (`AccountReadRepository`), the usual DI shape. Mediator dispatch
(`mediator.Send(new X())` → the `Handle` of `IRequestHandler<X, ..>`) through the generic arguments
of base lists: MediatR built in, an organization's own bus declared by its convention (core/dispatch.py).
"""

from __future__ import annotations

import re
from pathlib import Path

from tree_sitter import Node

from ...core.dispatch import DispatchRule
from ...core.model import FileInfo
from ...core.types import RepoTypes, Unknown
from ..base import LanguageSupport, PackageFactory, ResolveContext, node_text
from .http import CsScanner
from .locals import local_type, new_type, receiver_type as declared_receiver
from .type_facts import NAMESPACE_NODES, CsTypes, namespaces, type_facts
from .type_index import CsTypeIndex, qualified, ref as type_ref, written_type

HERE = Path(__file__).parent

FRAMEWORK_ROOTS = {"System", "Microsoft"}
_BUILTINS = frozenset({"Console", "Task", "String", "Enumerable", "Convert"})
# MediatR (`IMediator` / `ISender` / `IPublisher`): public, so on in every C# repo. Precise because the edge needs
# a handler of that exact message type in the repo. An organization's own bus goes in its convention.
_MEDIATR = (DispatchRule(frozenset({"Send"}), frozenset({"IRequestHandler"})),
            DispatchRule(frozenset({"Publish"}), frozenset({"INotificationHandler"})))
_DECORATOR_ENTRY = re.compile(r"\[(HttpGet|HttpPost|HttpPut|HttpDelete|HttpPatch|Route|Function|ServiceBusTrigger|QueueTrigger)\b")


_CS_PACKAGE_ID = re.compile(r"<PackageId>\s*([^<]+?)\s*</PackageId>")
_CS_ASSEMBLY_NAME = re.compile(r"<AssemblyName>\s*([^<]+?)\s*</AssemblyName>")
_CS_PACKAGE_REF = re.compile(r"<PackageReference\b([^>]*)/?>", re.S)
_CS_ATTR = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


class CSharpSupport(LanguageSupport):
    def module_prefix(self, file: FileInfo) -> str:
        return ""                                   # namespaces carry the scope

    def qualified_name(self, prefix: str, chain: list[str], name: str) -> str:
        return ".".join(chain + [name])

    def scope_chain(self, dnode: Node, src: bytes, chain: list[str], kind: str, file_namespace: str | None) -> list[str]:
        if file_namespace and not any(a.type in NAMESPACE_NODES for a in _ancestors(dnode)):
            return [file_namespace] + chain
        return chain

    def file_scope(self, root: Node, src: bytes) -> tuple[list[str], str | None]:
        return namespaces(root, src)

    # ---- static receiver types
    def file_facts(self, root: Node, src: bytes) -> CsTypes:
        return type_facts(root, src)

    def call_receiver(self, call: Node, receiver: Node, src: bytes) -> tuple[str, tuple[str, ...]] | None:
        return declared_receiver(call, receiver, src)

    def arity(self, node: Node, src: bytes) -> tuple[int, int | None] | None:
        pl = node.child_by_field_name("parameters") or next((c for c in node.children if c.type == "parameter_list"), None)
        if pl is None:
            return None
        required = optional = 0
        variadic = False
        for prm in pl.children:
            if prm.type == "params":                        # `params int[] rest`: any number more
                variadic = True
            elif prm.type == "parameter":
                if any(m.type == "modifier" and node_text(m, src) == "this" for m in prm.children):
                    continue                                # extension method: the receiver, not an argument
                if any(c.type == "=" for c in prm.children):
                    optional += 1
                else:
                    required += 1
        return (required, None if variadic else required + optional)

    def call_arg_count(self, call: Node, src: bytes) -> int | None:
        args = call.child_by_field_name("arguments")
        if args is None:
            return None
        return sum(1 for a in args.children if a.type == "argument")

    def call_argument_type(self, call: Node, src: bytes) -> str | None:
        args = call.child_by_field_name("arguments") if call.type == "invocation_expression" else None
        first = next((a for a in (args.children if args is not None else []) if a.type == "argument"), None)
        expr = next((c for c in (first.children if first is not None else []) if c.is_named), None)
        if expr is None:
            return None
        made = new_type(expr, src)
        if made or expr.type != "identifier":
            return made
        found = local_type(node_text(expr, src), call, src, prefer_new=True)
        return found if found and not found.startswith("call:") else None

    def message_handlers(self, ctx: ResolveContext, file: FileInfo, message_type: str,
                         handler_bases: frozenset[str]) -> list[str]:
        return self._types(ctx).handlers(file, message_type, handler_bases)

    def type_index(self, ctx: ResolveContext) -> CsTypeIndex:
        return CsTypeIndex(ctx)

    def _types(self, ctx: ResolveContext) -> CsTypeIndex:
        """The repo's C# type index: the one the HTTP pass shares, or one over this context."""
        if ctx.types is None:
            ctx.types = RepoTypes(ctx)
        return ctx.types.of(self.id)

    def resolve_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str, path: tuple[str, ...]) -> str | None:
        types = self._types(ctx)
        cur = written_type(types, file.path, receiver_type)
        for member in path:
            if isinstance(cur, Unknown):
                return None
            found = types.field(cur, member)
            cur = found.type if not isinstance(found, Unknown) else found
        return qualified(cur) if not isinstance(cur, Unknown) else None

    def external_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str, path: tuple[str, ...],
                          owner: str | None = None) -> str | None:
        """The type the receiver chain ends in is named and no type of this repo has that name: the receiver itself
        (`Substitute`, a `Fixture fixture`) or a member of a repo type (`ILogger _logger`). A name before a path
        (`Company.Shop.Infrastructure.Dependencies`: a namespace), an unknown member (inherited from a base
        outside the repo) or a name two repo types share says nothing, and so does a method's result."""
        types = self._types(ctx)
        if receiver_type.startswith("call:"):
            return None
        cur = types.type_named(receiver_type, file.path)
        if isinstance(cur, Unknown) and not path and owner:
            # `ParentId.IsEmpty()`: a capitalized name that is not a type may be a member the caller's type inherits —
            # from a base outside the repo too (`HttpContext` of a controller), and then nothing is known
            mt = types.inherited_member_type(owner, receiver_type)
            if mt is not None:
                return mt if mt and not types.is_type_name(mt) else None
        if isinstance(cur, Unknown):
            return receiver_type if not path and not types.is_type_name(receiver_type) else None
        for member in path:
            found = types.field(cur, member)
            if isinstance(found, Unknown):
                return None
            if isinstance(found.type, Unknown):
                return found.written if not types.is_type_name(found.written) else None
            cur = found.type
        return None

    def is_extension_method(self, ctx: ResolveContext, symbol, receiver_type: str | None = None, unknown: bool = False) -> bool:
        """An extension method that can take the receiver: with its type known, one extending that type; with it
        `unknown`, one extending what may be anything — an interface, a type parameter, `object`, a predefined type
        (`this WebApplicationFactory f` takes neither an `HttpClient` nor an unknown receiver)."""
        if symbol.kind != "method" or ctx.files_by_id[symbol.file_id].language != self.id:   # a homonym of another language
            return False
        for name, line, this_type, _ in CsTypes.of(ctx.facts.get(symbol.file_id)).extensions:
            if name == symbol.name and line == symbol.line_start:
                loose = not this_type or this_type == "object" or bool(re.match(r"^I[A-Z]", this_type))
                return loose or this_type == receiver_type if (receiver_type or unknown) else True
        return False

    def extension_methods(self, ctx: ResolveContext, symbols: list, qualified_type: str) -> list[tuple[list, str]]:
        """Those whose `this` takes the type or a base of it, an interface it names included, the nearest first. Failing
        that, the only one that takes any value; on a type with a base outside the repo, only when no other method of
        the repo has its name, since that base may declare the method."""
        types = self._types(ctx)
        chain, outside = types.ancestry(qualified_type)
        near: dict[int, list] = {}
        anything = []
        for s in symbols:
            takes = _takes(ctx, s)
            if takes == "object":
                anything.append(s)
            elif (far := _distance(types, chain, outside, ctx.files_by_id[s.file_id], takes)) is not None:
                near.setdefault(far, []).append(s)
        if near:
            return [(near[min(near)], "receiver-type")]
        return [(anything, "unique-name")] if len(anything) == 1 and (not outside or len(symbols) == 1) else []

    def manifest_deps(self, rel_path: str, text: str) -> tuple[list[str], list[tuple[str, str]]]:
        """.csproj: `<PackageId>` (else `<AssemblyName>`, else the file stem) publishes;
        `<PackageReference Include=".." Version="..">` requires. `<ProjectReference>` is intra-repo."""
        m = _CS_PACKAGE_ID.search(text) or _CS_ASSEMBLY_NAME.search(text)
        name = m.group(1).strip() if m else Path(rel_path).stem
        deps = []
        for ref in _CS_PACKAGE_REF.finditer(text):
            attrs = dict(_CS_ATTR.findall(ref.group(1)))
            inc = attrs.get("Include") or attrs.get("Update")
            if inc:
                deps.append((inc, attrs.get("Version", "")))
        return [name], deps

    def supertypes(self, ctx: ResolveContext, qualified_type: str) -> list[str]:
        return self._types(ctx).ancestry(qualified_type)[0][1:]

    def has_external_base(self, ctx: ResolveContext, qualified_type: str) -> bool:
        return bool(self._types(ctx).ancestry(qualified_type)[1])

    def implementation_target(self, ctx: ResolveContext, qualified_type: str, method: str,
                              from_type: str | None = None) -> str | None:
        types = self._types(ctx)
        chain = types.di_chain(qualified_type)
        if chain:
            if from_type in chain:                       # a decorator calling the instance it wraps: the next one inward
                i = chain.index(from_type)
                impl = chain[i - 1] if i > 0 else None
            else:
                impl = chain[-1]                         # anyone else gets the outermost
            if impl is None:
                return None
        else:
            impls = types.implementers(type_ref(qualified_type))
            if len(impls) != 1:
                return None
            impl = qualified(impls[0])
        explicit_for = types.explicit_interface(impl, method)
        if explicit_for and explicit_for != type_ref(qualified_type).name:
            return None          # `IOther.Method` explicit implementation: not what this interface's call reaches
        return impl

    def resolve_import(self, ctx: ResolveContext, file: FileInfo, spec: str, pkg: PackageFactory) -> tuple[str, str] | None:
        files = ctx.namespaces.get(spec)
        if files:
            # one edge per declaring file would explode on big namespaces; point at the first
            # file's module instead, which is the meaningful unit for C#.
            return (ctx.files_by_id[files[0]].module_id, "Module")
        root = spec.split(".")[0]
        return (pkg("nuget", spec, root in FRAMEWORK_ROOTS), "Package")


def _takes(ctx: ResolveContext, symbol) -> str | None:
    """What a value of a repo type must be to pass as the method's `this`; None when it is not an extension method."""
    return next((passes for name, line, _, passes in CsTypes.of(ctx.facts.get(symbol.file_id)).extensions
                 if name == symbol.name and line == symbol.line_start), None)


def _distance(types: CsTypeIndex, chain: list[str], outside: set[str], file: FileInfo, takes: str | None) -> int | None:
    """How far up the receiver's type `chain` the type an extension's `this` names is, read in the extension's file:
    its place in the repo's part of the chain, or past it for a base outside the repo; None when it is not there."""
    if not takes or takes == "object":
        return None
    t = types.lookup(file, takes)
    if t is not None:
        return chain.index(t.qualified) if t.qualified in chain else None
    return len(chain) if takes in outside else None


def _ancestors(node: Node):
    n = node.parent
    while n is not None:
        yield n
        n = n.parent


LANGUAGES = [
    CSharpSupport(
        id="csharp", grammar="csharp", extensions=(".cs",), query_file=HERE / "queries.scm", stack="dotnet",
        manifest_suffixes={".csproj": "csproj", ".fsproj": "fsproj"}, builtin_receivers=_BUILTINS, parent_receivers=frozenset({"base"}), ecosystem="nuget",
        http_scanner=CsScanner, namespace_nodes=NAMESPACE_NODES,
        entry_point_hints=("[HttpGet", "[HttpPost", "[HttpPut", "[HttpDelete", "[HttpPatch", "[Route", "IActionResult"),
        decorator_entry=_DECORATOR_ENTRY, dispatch=_MEDIATR,
    ),
]
