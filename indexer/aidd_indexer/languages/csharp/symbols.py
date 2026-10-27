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
from .locals import local_type, new_type, read_name, receiver_type as declared_receiver
from .type_facts import NAMESPACE_NODES, CsTypes, namespaces, type_facts
from .type_index import CsTypeIndex, qualified, ref as type_ref
from .type_syntax import bare
from .wiring import di_chain, handlers
from .written import arguments, follow, named, start

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
            return bare(made) if made else made
        found = local_type(node_text(expr, src), call, src, prefer_new=True)
        return bare(found) if found and not found.startswith("call:") else None

    def message_handlers(self, ctx: ResolveContext, file: FileInfo, message_type: str,
                         handler_bases: frozenset[str]) -> list[str]:
        return handlers(self._types(ctx), file, message_type, handler_bases)

    def type_index(self, ctx: ResolveContext) -> CsTypeIndex:
        return CsTypeIndex(ctx)

    def _types(self, ctx: ResolveContext) -> CsTypeIndex:
        """The repo's C# type index: the one the HTTP pass shares, or one over this context."""
        if ctx.types is None:
            ctx.types = RepoTypes(ctx)
        return ctx.types.of(self.id)

    def resolve_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str, path: tuple[str, ...]) -> str | None:
        types = self._types(ctx)
        cur, args = start(types, file.path, receiver_type)
        cur = follow(types, cur, path, args)
        return qualified(cur) if not isinstance(cur, Unknown) else None

    def external_receiver(self, ctx: ResolveContext, file: FileInfo, receiver_type: str,
                          path: tuple[str, ...]) -> tuple[str, bool] | None:
        """A type the receiver chain reaches is named and no type of this repo has that name: the receiver itself
        (`Substitute`, a `Fixture fixture`) or a member of a repo type (`ILogger _logger`, or `Logger` that a base
        declares); with whether the chain ends in it. A member after it (`_lazy.Value`) has a type the repo cannot read,
        so the receiver is not that one. A name before a path (`Company.Shop.Infrastructure.Dependencies`: a namespace),
        an unknown member or a name two repo types share says nothing, and so does a method's result."""
        types = self._types(ctx)
        if receiver_type.startswith("call:"):
            return None
        owner, name = read_name(receiver_type)
        cur, written = named(types, file.path, receiver_type)
        if isinstance(cur, Unknown):
            # `HttpContext.X()` in a controller: a base outside the repo may declare the name, and then nothing is known
            hidden = owner is not None and types.member(owner, name) is None and types.class_base_outside(owner)
            return (written, True) if not path and not hidden and not types.is_type_name(written) else None
        args = arguments(types, file.path, receiver_type)
        for i, member in enumerate(path):
            found, args = types.field(cur, member, args), ()
            if isinstance(found, Unknown):
                return None
            if isinstance(found.type, Unknown):
                return (found.written, i == len(path) - 1) if not types.is_type_name(found.written) else None
            cur = found.type
        return None

    def extension_fit(self, ctx: ResolveContext, symbol, package: str | None = None, ends: bool = False,
                      generic: bool = False) -> str | None:
        """How an extension method takes the receiver of a call only extensions can serve: one whose type is outside
        the repo (`package`, which the chain `ends` in or only passes through), or unknown. None for one extending
        another type than `package`, or than what may be anything (an interface, a type parameter, `object`, a
        predefined type): `this WebApplicationFactory f` takes neither an `HttpClient` nor an unknown receiver.
        "incompatible" when C# proves it cannot take the call: the call passes type arguments (`generic`) and neither
        it nor its block declares type parameters; or the receiver's type is outside the repo, which no type of the
        repo is, and the `this` is one. "compatible" when the `this` is the receiver's type or takes any value, and
        "unknown" otherwise."""
        if symbol.kind != "method" or ctx.files_by_id[symbol.file_id].language != self.id:   # a homonym of another language
            return None
        for name, line, this_type, passes, typed, arity in CsTypes.of(ctx.facts.get(symbol.file_id)).extensions:
            if name == symbol.name and line == symbol.line_start:
                if not (not this_type or this_type in ("object", package) or re.match(r"^I[A-Z]", this_type)):
                    return None
                if (generic and not typed) or (ends and this_type and this_type != package and self._types(ctx).lookup(
                        ctx.files_by_id[symbol.file_id], this_type, arity) is not None):
                    return "incompatible"
                return "compatible" if (ends and this_type == package) or passes == "object" else "unknown"
        return None

    def extension_methods(self, ctx: ResolveContext, symbols: list, qualified_type: str,
                          written: str = "") -> list[tuple[list, str]]:
        """Those whose `this` takes the type or a base of it, an interface it names included, the nearest first. Failing
        that, the only one that takes any value; on a type with a base outside the repo, only when no other method of
        the repo has its name, since that base may declare the method. A call on a type's name (`Type.M()`) has no
        value to extend."""
        types = self._types(ctx)
        owner, name = read_name(written)
        if written.startswith("name:") and (owner is None or types.member(owner, name) is None):
            return []
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
        chain = di_chain(types, qualified_type)
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
    return next((passes for name, line, _, passes, *_ in CsTypes.of(ctx.facts.get(symbol.file_id)).extensions
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
