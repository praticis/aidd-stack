"""Shared machinery for the per-language HTTP scanners (`languages/<lang>/http.py`).

A language scanner walks its tree and decides which calls are route registrations and which are outbound
requests — see `docs/indexer-evolution.md` for the rules table. `BaseScanner` gives it the rest:

- expressions → path templates and methods (`path_of`, `method_from_args`: `http_expr.PathExpressions`), over the
  file's name bindings (`http_scope.Scopes`) and the directory's constants (`PackageContext`);
- where a route lives: `prefix_for` (a closure region — the language's `region_of` — or a group variable),
  `route_path` (the root, constraints and converters, relative patterns on a group) and the mount graph
  (`mount`, settled by `finish` for the file: `http_mounts.MountGraph`; across files, `compose` follows the routers
  each file names for the others — `global_of` —, its imports — `read_imports`, resolved by `http_view.RepoView` —
  and the constants of the packages it imports, `foreign_const`);
- route vs. client (the main source of false positives): `is_handler_like` — a call is a *route registration*
  when the argument after the path is a function value, an *outbound call* when it is data;
- recording with evidence `repo:path:line` (`add_endpoint`, `add_call`). Test files and e2e/integration folders are
  skipped; outbound paths made only of placeholders are dropped. The linker decides which endpoint a call hits —
  here we only record what the code says.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath
from typing import NamedTuple

from tree_sitter import Node

from ..languages.base import node_text as text, walk  # noqa: F401 — walk is re-exported for the scanners
from . import ids
from .config import TEST_FILE  # noqa: F401 — re-exported for the scanners / integrations
from .http_expr import PathExpressions, collect_constants, first_string, unwrap_arg, valid_path  # noqa: F401 — re-exported
from .http_mounts import MountedRoot, MountGraph, RouterKey, compose as compose_mounts
from .http_nodes import (CALL_NODES, HANDLER_NODES, NAME_NODES, NON_HANDLER_NODES, STRING_NODES,  # noqa: F401
                         FUNCTION_SCOPES, has_interpolation, member)
from .http_scope import END, Scopes, scope_id
from .model import HttpCallInfo, HttpEndpointInfo, RepoInfo, SymbolInfo
from .scan_patterns import ScanPatterns  # noqa: F401 — re-exported for scanners / integrations
from .paths import (HTTP_METHODS, PATH_LITERAL, REL_PATH_LITERAL, has_literal_segment, is_url_literal, mask_placeholders,
                    normalize_path, path_key, unquote)


# --- outbound callee names -> method (None = look at the arguments) ---------------------------
OUTBOUND = {
    # Go helpers / net/http / resty
    "PostJSON": "POST", "GetJSON": "GET", "PutJSON": "PUT", "PatchJSON": "PATCH", "DeleteJSON": "DELETE",
    "DoJSON": None, "Do": None, "DoRequest": None, "Request": None, "Call": None, "Send": None, "Execute": None,
    "NewRequest": None, "NewRequestWithContext": None, "PostForm": "POST",
    # JS: axios / got / ky / superagent / fetch
    "fetch": None, "request": None, "$fetch": None, "ofetch": None,
    # C#: HttpClient
    "GetAsync": "GET", "GetStringAsync": "GET", "GetStreamAsync": "GET", "GetByteArrayAsync": "GET", "GetFromJsonAsync": "GET",
    "PostAsync": "POST", "PostAsJsonAsync": "POST", "PutAsync": "PUT", "PutAsJsonAsync": "PUT",
    "PatchAsync": "PATCH", "PatchAsJsonAsync": "PATCH", "DeleteAsync": "DELETE", "DeleteFromJsonAsync": "DELETE", "SendAsync": None,
    # Python: requests / httpx / aiohttp
    "get": "GET", "post": "POST", "put": "PUT", "patch": "PATCH", "delete": "DELETE", "head": "HEAD", "options": "OPTIONS",
    "Get": "GET", "Post": "POST", "Put": "PUT", "Patch": "PATCH", "Delete": "DELETE", "Head": "HEAD",
}
GENERIC_OUTBOUND = {"Do", "DoRequest", "Request", "Call", "Send", "Execute", "request", "SendAsync", "DoJSON"}
CLIENT_RECEIVER = re.compile(r"(client|cli|http|https|resty|api|axios|fetch|got|ky|superagent|gateway|adapter|hc|requests|httpx|session|sess|aiohttp)$", re.I)
IDENTIFIER = re.compile(r"^[A-Za-z_$][\w$]*$")
# a prefix the code does not fix: every segment a value read at runtime
# (`router.WithPrefix("/" + strings.Trim(opts.RoutePrefix, "/"))`), unlike a parameter it writes (`/:lang`)
RUNTIME_PREFIX = re.compile(r"^(/?\{param\})+/?$")


ROUTER_TYPE = re.compile(r"\b(Router|RouterGroup|Engine|Echo|Group|Mux|ServeMux|App|APIRouter|FastAPI|Flask|Blueprint|"
                         r"Starlette|Sanic|Quart)\b")     # a parameter's declared type that makes it a router


class Pending(NamedTuple):
    """What a file cannot finish alone: a route recorded as the file writes it whose prefix lives in another file, or
    a call to a method another file defines (`item` is then the call without its path). The language's `compose`
    resolves it from the facts every file published, after the whole repo is scanned."""
    item: HttpEndpointInfo | HttpCallInfo | None   # None: a request for routes the rule creates (inherited actions)
    rule: str               # which `compose` rule resolves it ("cs.inherited-route", "cs.client-wrapper", ..)
    key: tuple              # what that rule looks up


@dataclass
class HttpResult:
    endpoints: list[HttpEndpointInfo] = field(default_factory=list)
    calls: list[HttpCallInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # The per-file summaries composed after the scan — data only, never trees (F1.13): what a file publishes for the
    # others (`facts[kind][name]` → one entry per declaration) and the routes waiting on them.
    facts: dict[str, dict[str, list]] = field(default_factory=dict)
    pending: list[Pending] = field(default_factory=list)

    def publish(self, kind: str, name: str, fact) -> None:
        self.facts.setdefault(kind, {}).setdefault(name, []).append(fact)


def rebased(repo: RepoInfo, ep: HttpEndpointInfo, prefix: str) -> HttpEndpointInfo:
    """`ep` under `prefix` (a mount, an inherited route), with the id of its new path."""
    path = normalize_path(prefix.rstrip("/") + "/" + ep.path.lstrip("/"))
    return replace(ep, path=path, raw_pattern=str(ep.raw_pattern),
                   id=ids.http_endpoint(repo.tenant, repo.name, ep.method, path_key(path)))


def _is_root(ep: HttpEndpointInfo) -> bool:
    return isinstance(ep.raw_pattern, MountedRoot)


def replace_endpoints(out: HttpResult, plan: dict[int, list[HttpEndpointInfo]]) -> None:
    """Each endpoint whose `id()` is in `plan` gives way to what the plan lists there (nothing = dropped)."""
    if plan:
        out.endpoints = [new for ep in out.endpoints for new in plan.get(id(ep), [ep])]


class Region(NamedTuple):
    """A call that scopes the routes registered inside one of its closures (`BaseScanner.region_of`)."""
    outer: str              # the router the call is made on
    prefix: str             # what the closure's routes live under
    same_router: bool       # a registration on `outer` itself counts (gitea `m.Group("/x", func() { m.Get(..) })`)


# ------------------------------------------------------------------------------------------
class PackageContext:
    """Per directory (Go package / TS folder / C# namespace dir): route constants and env-var names."""

    def __init__(self, patterns: "ScanPatterns | None" = None) -> None:
        self.route_consts: dict[str, str] = {}     # name -> raw path (or base URL)
        self.const_parts: dict[str, list[tuple[str, str | None]]] = {}   # name -> `A + "/x"` as ("ref", "A"), ("lit", "/x")
        self.env_hints: set[str] = set()
        self.patterns = patterns or ScanPatterns()
        self.functions_by_name: dict[str, list[SymbolInfo]] = {}   # functions/methods of every file in the dir
        self.segments: dict[str, str] = {}          # name -> one path segment (`"cases"`): only whole, inside a template
        self.relatives: dict[str, str] = {}         # name -> segments without a leading slash (`"security/back-office"`):
                                                    # only C#'s routing attributes read them (`_RouteAttributes`)
        self.ambiguous: set[str] = set()            # a name two constants of the directory give different values
        self.passthrough: dict[str, int | None] = {}   # Go function → the parameter every `return` ends with
        self.verb_lists: dict[str, tuple[str, ...]] = {}   # Go `var MethodsPutPost = []string{http.MethodPut, ..}`
        self.file_facts: dict[str, dict] = {}       # file → its language's `file_facts` (Go: the struct field types)
        # Python class → (its bases' names, what its `__init__` hands `super().__init__` as the prefix): a router class
        # of the project (`class UserAPIRouter(APIRouter)`); None when two files of the directory define it differently
        self.classes: dict[str, tuple[tuple[str, ...], tuple | None] | None] = {}
        # TS/JS (file, name) → a client that puts a base before its paths: ("parts", the base) for
        # `axios.create({ baseURL })`, ("new", class, {option: parts}) for `new ApiClient(..)`, ("alias", name) for
        # `export default api`; and a class whose base is a field (`this.baseUrl = options.baseUrl || "/api"`) →
        # (the option that gives it, the default), None when two of the directory differ
        self.client_bases: dict[tuple[str, str], tuple] = {}
        self.client_classes: dict[str, tuple[str | None, list] | None] = {}
        self.client_rewritten: set[tuple[str, str]] = set()   # (file, client) a request interceptor rewrites the url of
        self._values: dict[str, object] = {}
        self.view = None                            # the repo around it (`http_view.RepoView`): imports, other dirs

    def define(self, name: str, raw: str | None = None, parts: list | None = None, segment: str | None = None,
               relative: str | None = None) -> None:
        if relative is not None:                    # read by name only where a template puts it — never a path alone
            if self.relatives.setdefault(name, relative) != relative:
                self.ambiguous.add(name)
            return
        value = raw if raw is not None else segment if segment is not None else tuple(parts or ())
        if self._values.setdefault(name, value) != value:
            self.ambiguous.add(name)
        if raw is not None:
            self.route_consts[name] = raw
        elif segment is not None:
            self.segments[name] = segment
        else:
            self.const_parts[name] = list(parts or ())

    def segment_const(self, name: str) -> str | None:
        """A constant holding one path segment, looked up as `route_const` does."""
        if "." in name:
            qualified = ".".join(name.split(".")[-2:])
            name = qualified if qualified in self.segments else name.split(".")[-1]
        return None if name in self.ambiguous else self.segments.get(name)

    def route_const(self, name: str, _seen: tuple[str, ...] = ()) -> str | None:
        """Raw path of a module-level constant; one built from others (`RouteItem = RouteCollection + "/{id}"`)
        is resolved on first use, since the constants it names may live in another file of the directory. `A.B`
        is looked up as `A.B` (a class constant), else as `B`; a name with two values in the directory is unknown."""
        if "." in name:
            qualified = ".".join(name.split(".")[-2:])
            name = qualified if qualified in self.route_consts or qualified in self.const_parts else name.split(".")[-1]
        if name in self.ambiguous:
            return None
        if name in self.route_consts:
            return self.route_consts[name]
        parts = self.const_parts.get(name)
        if parts is None or name in _seen or len(_seen) > 4:
            return None
        raw = self._joined(parts, _seen + (name,))
        if raw is not None:
            self.route_consts[name] = raw
        return raw

    def _joined(self, parts: list[tuple[str, str | None]], _seen: tuple[str, ...] = ()) -> str | None:
        """`A + "/x"` as parts, each constant by `route_const`; one the directory does not hold is a parameter, and a
        parameter at the start is a base (`{param}/api/v1` is `/api/v1`). None unless a path or a URL."""
        raw = ""
        for kind, v in parts:
            r = v if kind == "lit" else (self.route_const(v, _seen) if kind == "ref" and v else None)
            raw += r if r is not None else "{param}"
        raw = re.sub(r"^\{param\}(?=/)", "", raw)
        if len(raw) < 2 or not (PATH_LITERAL.match(mask_placeholders(raw)) or REL_PATH_LITERAL.match(raw) or is_url_literal(raw)):
            return None
        return raw

    def client_base(self, path: str, name: str, _depth: int = 0) -> str | None:
        """The base path the client `name` of the file `path` puts before its requests' paths (`client_bases`):
        docmost's `axios.create({ baseURL: "/api" })`, outline's `new ApiClient()` with `this.baseUrl =
        options.baseUrl || "/api"`. Only a path: a base URL's host is the linker's (`target_hint`)."""
        v = self.client_bases.get((path, name))
        if v is None or _depth > 3 or (path, name) in self.client_rewritten:
            return None
        if v[0] == "alias":
            return self.client_base(path, v[1], _depth + 1)
        if v[0] == "new":
            cls = self.client_classes.get(v[1])
            if cls is None:
                return None
            option, default = cls
            parts = (v[2].get(option) if option else None) or default
        else:
            parts = v[1]
        raw = self._joined(parts) if parts else None
        return raw if raw is not None and raw.startswith("/") else None


def dir_of(file_path: str) -> str:
    return str(PurePosixPath(file_path).parent)


_HINT_DIRS = ("outbound", "clients", "client", "gateways", "gateway", "integrations", "integration", "external",
              "providers", "provider", "adapters", "services", "service", "apis", "sdk", "connectors")


def target_hint(file_path: str) -> str:
    """'internal/adapters/outbound/billing/client.go' -> 'billing'; falls back to the dir name."""
    parts = PurePosixPath(file_path).parent.parts
    for i, part in enumerate(parts):
        if part.lower() in _HINT_DIRS and i + 1 < len(parts):
            nxt = parts[i + 1]
            if nxt.lower() not in ("http", "rest", "grpc", "outbound", "inbound", "v1", "v2"):
                return nxt
            if i + 2 < len(parts):
                return parts[i + 2]
    stem = PurePosixPath(file_path).stem
    m = re.match(r"^(.*?)[._-]?(client|service|api|gateway|adapter|http)$", stem, re.I)   # BillingClient.cs, users.service.ts
    if m and m.group(1):
        return m.group(1)
    return parts[-1] if parts else ""


def split_callee(callee: str) -> tuple[str, str, str]:
    """`a.b.c` → (method name `c`, receiver `a.b`, its last part `b`); no receiver → ("", "")."""
    name = callee.split(".")[-1]
    recv = callee.rsplit(".", 1)[0] if "." in callee else ""
    return name, recv, recv.split(".")[-1]


# ------------------------------------------------------------------------------------------
class BaseScanner(PathExpressions):
    relative_on_groups = False      # the framework joins a group prefix and a pattern without a leading slash (gin, MapGroup)
    mount_rule: str | None = None   # routers cross files (`global_of`): the `Pending` rule and the facts' kind prefix
    scope_declarations: frozenset[str] | None = None   # what declares a name in a function (`Scopes`); None: any assignment
    # a group other files can name (a package variable, a returned router, a router parameter) keeps its own prefix out
    # of what is registered on it here and publishes it as the router's: `compose` puts it on every chain through the
    # router, so routes of other files take it too (`APIv1 = router.Group("/api/v1")`, `r = r.Group("/v3")`)
    defer_global_group_prefix = False

    def __init__(self, repo: RepoInfo, fx, ctx: PackageContext, out: HttpResult):
        self.repo, self.fx, self.ctx, self.out = repo, fx, ctx, out
        self.src = fx.src
        self.scopes = Scopes(fx.tree.root_node, self.src, self.scope_declarations)
        self._path_memo: dict[tuple[int, bool], str | None] = {}   # `path_of` per (node, lenient)
        self.mounts = MountGraph()
        self.symbols_by_name: dict[str, list[SymbolInfo]] = {}
        for s in fx.symbols:
            self.symbols_by_name.setdefault(s.name, []).append(s)
        self.group_prefix: dict[RouterKey, str] = {}   # router/group variable -> path prefix (`group_key`)
        self.router_vars: set[str] = set()       # identifiers known to be routers/groups/apps
        self.app_vars: set[tuple[int, str]] = set()   # (scope, name) of the application itself, not a sub-router
        self.imports: dict[str, tuple[str, str | None]] = self.read_imports()   # local name -> (spec, name in it)
        self.foreign: list[tuple[str, RouterKey, str]] = []       # another file's router (global id) mounted here
        self.router_args: list[tuple[str, str, Node, str]] = []   # (parameter's global id, name, call, prefix added)
        self._functions_by_id: dict[int, Node] | None = None
        self._globals: dict[RouterKey, str | None] = {}
        self._closures: dict[RouterKey, RouterKey | None] = {}

    def scan(self) -> None:
        self.run()
        self.finish()

    def run(self) -> None:
        raise NotImplementedError

    def callee_of(self, fn: Node) -> str:
        """The callee as written, without whitespace (`requests\\n  .put`, `client.\\n\\tGet`)."""
        return re.sub(r"\s+", "", text(fn, self.src))

    def resolve_local(self, ident: Node) -> Node | None:
        """Value of the closest preceding assignment to this name in its scope (`Scopes.binding`)."""
        return self.scopes.binding(ident)[1]

    def mark_app(self, name: str, at: Node) -> None:
        """`name`, assigned at `at`, is the application (`gin.Default()`, `express()`, `FastAPI()`, `builder.Build()`)."""
        self.app_vars.add((scope_id(at), name))

    def is_app(self, name: str, at: Node) -> bool:
        return (scope_id(at), name) in self.app_vars

    # -- where a route lives: closure regions, groups, the file's mounts --------------------------
    def region_of(self, call: Node, fn: Node) -> Region | None:
        """Language hook: `fn` is an argument of `call`. When the call scopes the routes registered inside `fn` under
        a prefix — chi `r.Route("/x", func(r chi.Router) {...})`, fastify `register(fn, {prefix})` — say how."""
        return None

    def closure_uses(self, fn: Node, receiver: str) -> list[tuple[Node, str]]:
        """Language hook: `fn` is a function literal the code keeps under a name and that registers routes on
        `receiver`, a router from around it. Each place the code uses that name (a call inside a group, or the body of
        a group on `receiver`), with what it adds to `receiver`'s prefix there."""
        return []

    def _named_closure(self, f: Node, receiver: str, at: Node) -> RouterKey | None:
        """The router for routes registered at `at` on `receiver`, a router from outside the named closure `f`: one of
        `f`'s own, mounted at each use of the closure under that use's prefix, so a helper called in several groups
        gives its routes once per group. None when `receiver` is bound inside `f`, or no use of `f` is known."""
        key = (f.id, receiver)
        if key not in self._closures:
            self._closures[key] = None
            outer = self.scopes.binding_scope(receiver, f) == self.scopes.binding_scope(receiver, at)
            uses = self.closure_uses(f, receiver) if outer else []
            for use, added in uses:
                self.mounts.mount(key, self.router_key(receiver, use), (self.prefix_for(receiver, use) or "").rstrip("/") + added)
            self._closures[key] = key if uses else None
        return self._closures[key]

    def prefix_for(self, receiver: str, at: Node) -> str | None:
        """Prefix of a registration on `receiver` at `at`: the enclosing closure region's, else the group variable's;
        None when the receiver is neither (a plain router, the application). In a named closure, the prefix of each use
        comes on the edges of its router (`_named_closure`)."""
        f = at.parent
        while f is not None:
            if f.type in HANDLER_NODES and f.parent is not None and f.parent.parent is not None \
                    and f.parent.parent.type in CALL_NODES:
                region = self.region_of(f.parent.parent, f)
                if region is not None and (self.scopes.is_parameter(f, receiver)
                                           or (region.same_router and receiver == region.outer)):
                    base = self.prefix_for(region.outer, f.parent.parent) or ""
                    return base.rstrip("/") + region.prefix
            if f.type in HANDLER_NODES and self._named_closure(f, receiver, at) is not None:
                return ""
            f = f.parent
        key = self.group_key(receiver, at)
        own = self.group_prefix.get(key)
        if own is not None and self.defer_global_group_prefix and self.mount_rule and self._global(key) is not None:
            return ""                                  # published by `finish`, applied by `compose`
        return own

    def group_key(self, name: str, at: Node) -> RouterKey:
        """A group variable is the one the function around `at` binds: a parameter named like another function's group
        is another router (vikunja `a := e.Group("/api/v1"); registerAPIRoutes(a)`, whose `a` takes the prefix from the
        call). A field or an expression (`api.BaseRoutes.Users`, `g.Group("/x").Use(mw)`) is the file's."""
        return (self.scopes.binding_scope(name, at) if IDENTIFIER.match(name) else 0), name

    def router_key(self, name: str, at: Node) -> RouterKey:
        """The router `name` is at `at`. A closure region's router parameter is the outer router — chi's
        `r.Route("/x", func(r chi.Router) {...})`: the region's prefix is already in what is registered there."""
        f = at.parent
        while f is not None:
            if f.type in HANDLER_NODES and f.parent is not None and f.parent.parent is not None \
                    and f.parent.parent.type in CALL_NODES and self.scopes.is_parameter(f, name):
                region = self.region_of(f.parent.parent, f)
                return self.router_key(region.outer, f.parent.parent) if region is not None else (f.id, name)
            if f.type in HANDLER_NODES:
                key = self._named_closure(f, name, at)
                if key is not None:
                    return key
            f = f.parent
        return self.scopes.binding_scope(name, at), name

    def mount(self, child: str, child_at: Node, parent: str, at: Node, prefix: str, derived: bool = False) -> None:
        """`parent.use('/api', child)`, `parent.Mount("/x", child)`, `parent.include_router(child, prefix=...)`: the
        edge carries the parent's own group/closure prefix too. `derived`: `child := parent.Group("/x")`, whose
        prefix already holds the parent's — the edge only carries the mounts above the parent."""
        if not derived:
            prefix = (self.prefix_for(parent, at) or "").rstrip("/") + prefix
        self.mounts.mount(self.router_key(child, child_at), self.router_key(parent, at), prefix)

    def finish(self) -> None:
        """Prefix the routes of every router this file mounts; drop a sub-router's root that stays unmounted. With
        `mount_rule`, a route on a router other files can name waits for `compose`, and the file publishes its mounts
        of such routers."""
        glob = self._global if self.mount_rule else (lambda _: None)
        waiting, edges = self.mounts.settle(self.out.endpoints, lambda ep, prefix: rebased(self.repo, ep, prefix),
                                            _is_root, glob, self.foreign + self._router_args() if self.mount_rule else [],
                                            lambda key: key in self.app_vars)
        if self.mount_rule:
            self.out.pending.extend(Pending(ep, self.mount_rule, (g,)) for ep, g in waiting)
            for child, parent, prefix in edges:
                self.out.publish(f"{self.mount_rule}.edge", child, (parent, prefix))
            if self.defer_global_group_prefix:
                self._publish_own_prefixes()
            for key in self.app_vars:
                g = self._global(key)
                if g is not None:                             # an application other files can name
                    self.out.publish(f"{self.mount_rule}.app", g, True)

    def _publish_own_prefixes(self) -> None:
        """The prefix of each group of this file that other files can name, as that router's own."""
        for key, prefix in self.group_prefix.items():
            g = self._global(key) if prefix else None
            if g is not None:
                self.out.publish(f"{self.mount_rule}.own", g, prefix)

    @classmethod
    def compose(cls, out: HttpResult, repo: RepoInfo, view=None) -> None:
        """Language hook, once per repo after every file is scanned: resolve the `out.pending` routes of this language
        from `out.facts`. By default, the routes waiting on a router another file mounts (`mount_rule`)."""
        if cls.mount_rule is None:
            return
        waiting = [(p.item, p.key[0]) for p in out.pending if p.rule == cls.mount_rule]
        if waiting:
            edges = {child: list(dict.fromkeys(facts)) for child, facts in out.facts.get(f"{cls.mount_rule}.edge", {}).items()}
            apps = set(out.facts.get(f"{cls.mount_rule}.app", {}))
            owns = out.facts.get(f"{cls.mount_rule}.own", {})
            replace_endpoints(out, compose_mounts(waiting, edges, lambda ep, prefix: rebased(repo, ep, prefix), _is_root,
                                                  apps, owns))

    # -- what crosses files: imports, routers other files name -----------------------------------
    def read_imports(self) -> dict[str, tuple[str, str | None]]:
        """Language hook: local name → (import spec, the name it has in the imported module, or None for the module
        itself)."""
        return {}

    def resolve_import(self, spec: str) -> str | None:
        """Repo path of the file or package directory an import of this file names."""
        view = self.ctx.view
        return view.resolve(self.fx.file, spec) if view is not None else None

    def foreign_const(self, name: str, segment: bool = False) -> str | None:
        """`pkg.NAME` (or `NAME` imported by name), the import being of this repo: the constant as the directory of
        the imported file or package defines it — `model.APIURLSuffix`, `settings.API_V1_STR`, the enum member
        `RouteKey.Asset` (`RouteKey` imported by name). `segment`: a single word counts too (a Nest controller's)."""
        head, _, rest = name.partition(".")
        spec, orig = self.imports.get(head) or (None, None)
        if spec is None or not (rest or orig):
            return None
        target = self.resolve_import(spec)
        ctx = self.ctx.view.constants(target) if target is not None else None
        if ctx is None:
            return None
        for nm in ([f"{orig}.{rest}"] if orig and rest and orig != "default" else []) + [rest or orig]:
            found = ctx.route_const(nm) or (ctx.segment_const(nm) if segment else None)
            if found is not None:
                return found
        return None

    def global_of(self, key: RouterKey) -> str | None:
        """Language hook: the id other files know this router by (`http_mounts`), or None."""
        return None

    def _global(self, key: RouterKey) -> str | None:
        if key not in self._globals:
            self._globals[key] = self.global_of(key)
        return self._globals[key]

    def function_of(self, scope: int) -> Node | None:
        """The function a `RouterKey`'s scope id names."""
        if self._functions_by_id is None:
            self._functions_by_id = {n.id: n for n in walk(self.fx.tree.root_node) if n.type in FUNCTION_SCOPES}
        return self._functions_by_id.get(scope)

    def returns_name(self, fn: Node, name: str) -> bool:
        """`fn` has a `return name` (a closure's returns are its own)."""
        stack = [c for c in fn.children]
        while stack:
            d = stack.pop()
            if d.type in FUNCTION_SCOPES:
                continue
            if d.type == "return_statement":
                vals = [c for c in walk(d) if c.is_named and c is not d and c.type not in ("expression_list",)]
                if len(vals) == 1 and vals[0].type == "identifier" and text(vals[0], self.src) == name:
                    return True
            stack.extend(d.children)
        return False

    def module_binds(self, name: str) -> bool:
        return self.scopes.assigned_before(self.scopes.root, END, name) is not None

    def router_param_type(self, fn: Node, name: str) -> str | None:
        """Language hook: the declared type of `fn`'s parameter `name`, None when it is not one."""
        return None

    def is_router_param(self, name: str, at: Node) -> bool:
        """`name` at `at` is a parameter of an enclosing function typed as a router (`rg *gin.RouterGroup`)."""
        f = at.parent
        while f is not None:
            if f.type in FUNCTION_SCOPES:
                typ = self.router_param_type(f, name)
                if typ is not None:
                    return bool(ROUTER_TYPE.search(typ))
            f = f.parent
        return False

    def _router_args(self) -> list[tuple[str, RouterKey, str]]:
        """The router arguments of function calls as (global id of the parameter, the router, its prefix at the
        call), kept when the argument is a router of this file — by name first, the key only for those."""
        if not self.router_args:
            return []
        known = {r for _, r in self.mounts.routes} | {k for c, p, _ in self.mounts.edges for k in (c, p)} | \
            {p for _, p, _ in self.foreign} | self.app_vars
        names = {k[1] for k in known} | self.router_vars
        out = []
        for g, name, at, extra in self.router_args:
            if name in names or self.is_router_param(name, at):
                key = self.router_key(name, at)
                if key in known or name in self.router_vars or self.is_router_param(name, at):
                    out.append((g, key, (self.prefix_for(name, at) or "").rstrip("/") + extra))
        return out

    def route_path(self, n: Node, receiver: str, at: Node) -> str | None:
        """Pattern of a route registration on `receiver` (the call is `at`): what `path_of` accepts, plus what
        only a route pattern can be —
        - the root (`"/"`, `""`) when its full path is known: the receiver is the application itself or has a
          prefix of its own. A sub-router's root is wherever it gets mounted: `MountedRoot`, kept only if this
          file mounts it;
        - placeholders with constraints, converters or optional markers (`{id:int?}`, `{name:minlength(1)}`,
          `{slug:[a-z-]+}`, `<int:id>`, `<any(a, b):page>`, `:id?`);
        - on a group, a pattern without the leading slash (`v1.GET("users")`, `api.MapGet("{orderId:int}")`) — only where
          the framework joins them (`relative_on_groups`): Flask, Starlette and Express require the slash."""
        pre = self.prefix_for(receiver, at)
        p = self.path_of(n)
        if p is not None:
            return "/" + p if self.relative_on_groups and not p.startswith(("/", "http")) and pre is not None else p
        if n.type not in STRING_NODES or n.type == "interpolated_string_expression" or has_interpolation(n):
            return None
        lit = unquote(text(n, self.src)).strip()
        if lit in ("", "/"):
            return "/" if pre or self.is_app(receiver, at) else MountedRoot("/")
        masked = mask_placeholders(lit)
        if PATH_LITERAL.match(masked):
            return lit
        if self.relative_on_groups and pre is not None and PATH_LITERAL.match("/" + masked):
            return "/" + lit
        return None

    def route_chain(self, n: Node, builders: set[str], verbs: dict[str, str]) -> tuple[str, Node, Node] | None:
        """A verb of a route chain — gitea `m.Combo("/x").Get(h).Put(h)`, express `router.route('/x').get(h).post(h)`:
        every verb is a route on the builder's path. (the verb's method, the builder call, its receiver) when `n` is
        one, whatever verbs come between them; None otherwise."""
        obj, field = member(n.child_by_field_name("function"))
        method = verbs.get(text(field, self.src)) if field is not None else None
        while method is not None and obj is not None and obj.type in CALL_NODES:
            recv, link = member(obj.child_by_field_name("function"))
            name = text(link, self.src) if link is not None else ""
            if name in builders and recv is not None:
                return method, obj, recv
            if name not in verbs:
                return None
            obj = recv
        return None

    # -- route vs. client ----------------------------------------------------------------------
    def convention_call(self, n: Node, name: str, recv_last: str, callee: str, arg_nodes: list[Node]) -> bool:
        """Route registrars / client methods declared by a convention (`ScanPatterns`). Called first by
        every language scanner; True = recorded (or deliberately ignored), stop here."""
        pats = self.ctx.patterns
        if name in pats.registrars and len(arg_nodes) >= 2:
            fixed = pats.registrars[name]
            path_idx = next((i for i, a in enumerate(arg_nodes) if self.path_of(a) is not None), None)
            if path_idx is not None:
                method = fixed or self.method_from_args(arg_nodes[:path_idx + 1]) or "ANY"
                handler = next((a for a in reversed(arg_nodes) if self.is_handler_like(a)), None)
                self.add_endpoint(n, method, self.path_of(arg_nodes[path_idx]) or "", "convention", handler, router=recv_last)
                return True
        if name in pats.clients or (name in GENERIC_OUTBOUND and pats.is_client(recv_last)):
            method = pats.clients.get(name) or OUTBOUND.get(name) or self.method_from_args(arg_nodes)
            for a in arg_nodes:
                p = self.path_of(a, lenient=True)
                if p is not None:
                    self.add_call(n, method, p, callee)
                    return True
        return False

    def is_handler_like(self, n: Node | None) -> bool:
        """The argument after a route path: a function value, not data."""
        if n is None:
            return False
        n = unwrap_arg(n)
        if n.type in HANDLER_NODES:
            return True
        if n.type in NON_HANDLER_NODES:
            return False
        txt = text(n, self.src)
        if n.type in NAME_NODES:
            return not txt.lower() in ("nil", "null", "none", "undefined") and not re.search(r"\b(ctx|context|req|request|body|payload|opts|options|params|headers)\b$", txt, re.I)
        if n.type in CALL_NODES:
            # http.HandlerFunc(x), middleware(h), wrap(h), timeout(5, h) → handler-ish; fmt.Sprintf/data builders → not
            return not re.search(r"\b(Sprintf|Errorf|Marshal|Join|format|Encode|Serialize|bytes\.|strings\.)", txt)
        return False

    # -- handlers --------------------------------------------------------------------------------
    def _function_symbol(self, name: str):
        """The function a handler name refers to: this file first, else the only one with that name
        in the directory (a Go package / a controller folder spans files); two homonyms → None."""
        cands = [c for c in self.symbols_by_name.get(name) or [] if c.kind in ("function", "method")]
        if cands:
            return cands[0]
        pkg = self.ctx.functions_by_name.get(name) or []
        return pkg[0] if len(pkg) == 1 else None

    def _handler_in_call(self, call: Node, depth: int = 0):
        """`mw(h, WithX())`, `http.HandlerFunc(h)`, `chain(a, b)(h)`: the first argument (depth-first,
        the callee of a curried call included) that names a function of this repo. Option calls
        with no function argument (`WithX()`) are skipped."""
        if depth > 3:
            return None
        fn = call.child_by_field_name("function")
        args = call.child_by_field_name("arguments")
        kids = [c for c in args.children if c.is_named] if args is not None else []
        if fn is None:                       # C#
            named = [c for c in call.children if c.is_named]
            fn = named[0] if named else None
            al = next((c for c in named if c.type == "argument_list"), None)
            kids = [unwrap_arg(c) for c in al.children if c.is_named] if al is not None else []
        for a in kids:
            a = unwrap_arg(a)
            if a.type in HANDLER_NODES:
                return "<inline>", None
            if a.type in NAME_NODES:
                sym = self._function_symbol(text(a, self.src).split(".")[-1])
                if sym is not None:
                    return sym.name, sym.id
            elif a.type in CALL_NODES:
                found = self._handler_in_call(a, depth + 1)
                if found:
                    return found
        if fn is not None and fn.type in CALL_NODES:
            return self._handler_in_call(fn, depth + 1)
        return None

    def resolve_handler(self, handler_node: Node | None) -> tuple[str | None, str | None]:
        if handler_node is None:
            return None, None
        node = unwrap_arg(handler_node)
        if node.type in HANDLER_NODES:
            return "<inline>", None
        if node.type in CALL_NODES:
            found = self._handler_in_call(node)
            if found:
                return found
        txt = text(node, self.src).strip()
        m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*\)*\s*$", txt)
        name = m.group(1) if m else None
        if not name or name.lower() in ("nil", "null", "none"):
            return None, None
        sym = self._function_symbol(name)
        return name, (sym.id if sym else None)

    # -- recording -------------------------------------------------------------------------------
    def evidence(self, node: Node) -> str:
        return f"{self.repo.name}:{self.fx.file.path}:{node.start_point[0] + 1}"

    def add_endpoint(self, node: Node, method: str, raw_pattern: str, framework: str, handler_node: Node | None,
                     prefix: str | None = None, handler_name: str | None = None, handler_id: str | None = None,
                     router: str | None = None) -> HttpEndpointInfo | None:
        """`router`: the receiver the route is registered on — its prefix (`prefix_for`) applies, and a mount later
        in the file prefixes it again. `prefix`: given when there is no router (a Nest controller's). Returns the
        route recorded (None for a sub-router root nothing can mount)."""
        if router is not None:
            if prefix is None:
                prefix = self.prefix_for(router, node) or ""
            self.mounts.register(len(self.out.endpoints), self.router_key(router, node))
        elif isinstance(raw_pattern, MountedRoot):
            return None
        prefix = prefix or ""
        pat = (raw_pattern or "").strip()
        m = re.match(r"^([A-Z]+)\s+(/.*)$", pat)
        if m and m.group(1) in HTTP_METHODS:
            method, pat = m.group(1), m.group(2)
        full = (prefix.rstrip("/") + "/" + pat.lstrip("/")) if prefix else pat
        if handler_name is None and handler_node is not None:
            handler_name, handler_id = self.resolve_handler(handler_node)
        ep = self.endpoint_info(node, method, full, framework, handler_name, handler_id, raw_pattern=raw_pattern)
        self.out.endpoints.append(ep)
        return ep

    def endpoint_info(self, node: Node, method: str | None, raw: str, framework: str, handler_name: str | None = None,
                      handler_id: str | None = None, raw_pattern: str | None = None) -> HttpEndpointInfo:
        """The route at `node` (`raw`: its full path), not recorded — what a file publishes for another to take
        (inherited actions). `raw_pattern`: as written, when the path holds a prefix too."""
        path = normalize_path(raw)
        written = raw if raw_pattern is None else raw_pattern
        return HttpEndpointInfo(
            id=ids.http_endpoint(self.repo.tenant, self.repo.name, method or "ANY", path_key(path)),
            method=method or "ANY", path=path, raw_pattern=written if isinstance(written, MountedRoot) else str(written),
            framework=framework, file_id=self.fx.file.id,
            line=node.start_point[0] + 1, handler_name=handler_name, handler_id=handler_id, evidence=self.evidence(node),
        )

    def add_call(self, node: Node, method: str | None, raw_path: str, via: str) -> bool:
        """Record the outbound call at `node`; False when its path names no segment."""
        c = self.call_info(node, method, raw_path, via)
        if c is not None:
            self.out.calls.append(c)
        return c is not None

    def call_info(self, node: Node, method: str | None, raw_path: str, via: str) -> HttpCallInfo | None:
        """The outbound call at `node`; None when its path names no segment. With an empty `raw_path`, the call still
        waiting on its path (a `Pending` one)."""
        path = normalize_path(raw_path) if raw_path else ""
        if raw_path and not has_literal_segment(path):
            return None
        caller = self.fx._enclosing_symbol(node)
        return HttpCallInfo(
            id=ids.http_call(self.repo.tenant, self.repo.name, self.repo.ref, self.fx.file.path, node.start_point[0] + 1),
            method=(method or "ANY").upper(), path=path, raw_path=raw_path, via=via[-60:],
            target_hint=target_hint(self.fx.file.path), env_hints=sorted(self.ctx.env_hints),
            file_id=self.fx.file.id, line=node.start_point[0] + 1,
            caller_id=caller.id if caller else self.fx.file.id, evidence=self.evidence(node),
        )

    # -- shared: `x := r.Group("/v1")` style prefix tracking -------------------------------
    def group_path(self, n: Node) -> str | None:
        """The path a group or prefix call adds: what `path_of` reads, except a prefix only known at runtime, which the
        routes do not take, since a `/{param}/x` route would link to nothing."""
        p = self.path_of(n)
        return None if p is not None and RUNTIME_PREFIX.match(p) else p

    def _record_group(self, names: list[str], call: Node, fn_text: str, arg_nodes: list[Node]) -> None:
        recv = (fn_text.rsplit(".", 1)[0] if "." in fn_text else "").split(".")[-1]
        base = self.prefix_for(recv, call) or ""
        p = self.group_path(arg_nodes[0]) if arg_nodes else None
        p = p if p is not None else ""
        for nm in names:
            self.group_prefix[self.group_key(nm, call)] = (base.rstrip("/") + p) if p else base
            self.router_vars.add(nm)
            if recv:                                  # the group follows its parent wherever the file mounts it
                self.mount(nm, call, recv, call, "", derived=True)
