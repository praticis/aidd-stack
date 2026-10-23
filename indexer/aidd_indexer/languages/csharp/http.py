"""C# / ASP.NET Core: attribute-routed controllers — the `[Route]` their base classes carry, the actions those declare
(`[NonAction]` and overloads as the framework counts them), the project's own routing attributes
(`IRouteTemplateProvider`, subclasses of `RouteAttribute` / `Http*Attribute`), an action with `[Route]` and no verb as
ANY, Asp.Versioning's `{version:apiVersion}`, OData's routing conventions and a route token of the project with the
value its model convention is registered with —, endpoint classes (FastEndpoints, Ardalis.ApiEndpoints) and minimal
APIs (MapGroup chains); HttpClient.*Async, HttpRequestMessage, Refit, Flurl, RestSharp outbound."""

from __future__ import annotations

import re
from dataclasses import replace

from tree_sitter import Node

from ...core.http_base import (BaseScanner, HttpResult, OUTBOUND, Pending, STRING_NODES, first_string, rebased,
                               replace_endpoints, split_callee, text, valid_path, walk)
from ...core.http_expr import owner_class
from ...core.http_nodes import CLASS_NODES, has_interpolation
from ...core.http_scope import enclosing_function
from ...core.http_wrappers import param_shape, wrapped_path
from ...core.model import RepoInfo
from ...core import ids
from ...core.types import Unknown
from .locals import receiver_type
from .type_index import start_of
from .http_facts import (Action, Area, AreaRoute, AttrAction, AttrActionRoute, CharArray, ClientWrapper,
                         ClientWrapperCall, ConventionUse, CsClass, DefaultApiVersion, DefaultVersionRoute, FastBase,
                         FastEndpointRoutes, FeGroup, FeGroupRoute, FePrefix, FePrefixOverride, InheritedActions,
                         InheritedRoute, NonAction, RouteAttr, RouteConvention)
from ...core.paths import (HTTP_METHODS, PATH_LITERAL, VERB_BY_NAME, mask_placeholders, normalize_path, path_key,
                           unquote)

CS_MAP = {"MapGet": "GET", "MapPost": "POST", "MapPut": "PUT", "MapPatch": "PATCH", "MapDelete": "DELETE", "MapMethods": None, "Map": "ANY"}
CS_HTTP_ATTR = {"HttpGet": "GET", "HttpPost": "POST", "HttpPut": "PUT", "HttpPatch": "PATCH", "HttpDelete": "DELETE", "HttpHead": "HEAD", "HttpOptions": "OPTIONS"}
ENDPOINT_BASE = re.compile(r"^(EndpointBase(Sync|Async)?|BaseEndpoint|BaseAsyncEndpoint)$")   # Ardalis.ApiEndpoints
FAST_ENDPOINT = re.compile(r"^(Endpoint|EndpointWithoutRequest|EndpointWithMapping|EndpointWithMapper|Ep)$")
FE_VERBS = {"Get": "GET", "Post": "POST", "Put": "PUT", "Patch": "PATCH", "Delete": "DELETE", "Head": "HEAD", "Options": "OPTIONS"}
ROUTE_ATTR_BASES = {"Route": None, **CS_HTTP_ATTR}      # a framework routing attribute a project's own derives from → verb
ROUTE_PROVIDERS = {"IRouteTemplateProvider", "IActionHttpMethodProvider"}
# the framework's attributes, never a routing attribute of the project (`_attr_uses` skips them)
FRAMEWORK_ATTRS = {"Route", "RoutePrefix", "ApiController", "Controller", "NonController", "NonAction", "Area", "ApiVersion",
                   "MapToApiVersion", "Authorize", "AllowAnonymous", "ApiExplorerSettings", "Produces", "Consumes",
                   "ProducesResponseType", "ProducesDefaultResponseType", "Tags", "EnableCors", "DisableCors", "Obsolete",
                   "ResponseCache", "ValidateAntiForgeryToken", "IgnoreAntiforgeryToken", "RequestSizeLimit",
                   "DisableRequestSizeLimit", "ServiceFilter", "TypeFilter", "FormatFilter", "OutputCache",
                   "EnableRateLimiting", "DisableRateLimiting", "EndpointSummary", "EndpointDescription", "AcceptVerbs"}
ODATA_VERBS = {"Get": "GET", "Post": "POST", "Put": "PUT", "Patch": "PATCH", "Delete": "DELETE"}
API_VERSION = re.compile(r"\{\w+:apiVersion\}", re.I)    # Asp.Versioning's URL segment: `v{version:apiVersion}`
API_VERSION_NAME = re.compile(r"\{(\w+):apiVersion\}", re.I)
AREA_TOKEN = re.compile(r"\[area\]|\{area\}", re.I)
MODEL_CONVENTIONS = {"IApplicationModelConvention", "IControllerModelConvention", "IActionModelConvention"}
ROUTE_TOKEN = re.compile(r"\[(\w+)\]")
FRAMEWORK_TOKENS = {"controller", "action", "area", "page", "handler"}
TOKEN_VALUE = re.compile(r"^[A-Za-z0-9_.~\-/]*$")
FLURL_VERBS = {"GetAsync": "GET", "GetJsonAsync": "GET", "GetStringAsync": "GET", "GetStreamAsync": "GET",
               "PostAsync": "POST", "PostJsonAsync": "POST", "PostStringAsync": "POST", "PostUrlEncodedAsync": "POST",
               "PutAsync": "PUT", "PutJsonAsync": "PUT", "PatchAsync": "PATCH", "PatchJsonAsync": "PATCH",
               "DeleteAsync": "DELETE", "HeadAsync": "HEAD", "OptionsAsync": "OPTIONS"}


class CsScanner(BaseScanner):
    """ASP.NET Core: attribute-routed controllers + minimal APIs; HttpClient / Refit outbound."""
    relative_on_groups = True

    def __init__(self, *args) -> None:
        super().__init__(*args)

    def run(self) -> None:
        if b"NSwag toolchain" in self.src[:4096]:           # a generated client: each operation, read whole
            for n in walk(self.fx.tree.root_node):
                if n.type == "method_declaration":
                    self._nswag_operation(n)
            return
        for n in walk(self.fx.tree.root_node):
            if n.type == "class_declaration":
                self._controller(n)
            elif n.type == "assignment_expression":
                self._default_api_version(n)
                self._fe_route_prefix(n)
            elif n.type == "interface_declaration":
                self._refit(n)
            elif n.type == "variable_declarator":
                self._maybe_group(n)
            elif n.type == "field_declaration":
                self._char_array(n)
            elif n.type == "invocation_expression":
                self._route_convention_use(n)
                self._invocation(n)
            elif n.type == "object_creation_expression":
                self._request_message(n)

    # -- helpers ------------------------------------------------------------------------------
    def _attrs(self, n: Node) -> list[tuple[str, str | None, Node]]:
        """(name, first string arg or None, attribute node) for every attribute on a declaration."""
        out = []
        for al in n.children:
            if al.type != "attribute_list":
                continue
            for a in al.children:
                if a.type != "attribute":
                    continue
                nm = next((c for c in a.children if c.type in ("identifier", "qualified_name", "generic_name")), None)
                args = next((c for c in a.children if c.type == "attribute_argument_list"), None)
                lit = None
                if args is not None:
                    first = next((c for c in args.children if c.type == "attribute_argument"), None)
                    if first is not None:
                        s = first_string(first, self.src)
                        expr = first.named_children[-1] if first.named_child_count else None
                        if s is None and expr is not None and expr.type == "string_literal" and not unquote(text(expr, self.src)):
                            s = ""                              # `[HttpGet("")]`: an empty template, written out
                        if expr is not None and expr.type == "interpolated_string_expression":
                            r = self._recipe(expr, {})          # `$"{{{nameof(id)}:guid}}"` → `{id:guid}`
                            if r is not None and all(part[0] == "lit" for part in r):
                                s = "".join(part[1] for part in r)
                        elif s is None and expr is not None and expr.type in ("identifier", "member_access_expression"):
                            owner = n                           # `[Route(LoginPath)]`: a constant of the class
                            while owner is not None and owner.type != "class_declaration":
                                owner = owner.parent
                            r = self._recipe(expr, {}, owner)
                            if r is not None and all(part[0] == "lit" for part in r):
                                s = "".join(part[1] for part in r)
                        if s is not None and not re.match(r"^(Name|Order)\s*=", text(first, self.src)):
                            lit = _aspnet_template(s)
                name = text(nm, self.src) if nm is not None else ""
                if nm is not None and nm.type == "qualified_name":      # `[Microsoft.AspNetCore.Mvc.HttpGet("..")]`
                    name = name.split(".")[-1]
                out.append((name.removesuffix("Attribute") if name != "Attribute" else name, lit, a))
        return out

    def _bases(self, cls: Node) -> list[str]:
        """The base types as dotted names without type arguments: `Endpoint<Req, Res>` → `Endpoint`,
        `EndpointBaseAsync.WithRequest<R>.WithActionResult<T>` → `EndpointBaseAsync.WithRequest.WithActionResult`."""
        bl = next((c for c in cls.children if c.type == "base_list"), None)
        out = []
        for b in (c for c in bl.children if c.is_named) if bl is not None else ():
            name = re.sub(r"\s+", "", text(b, self.src)).split("(")[0]
            while re.search(r"<[^<>]*>", name):
                name = re.sub(r"<[^<>]*>", "", name)
            out.append(name.removeprefix("global::"))
        return out

    def _controller(self, cls: Node) -> None:
        attrs = self._attrs(cls)
        prefixes = [lit for name, lit, _ in attrs if name in ("Route", "RoutePrefix") and lit is not None]
        cname = cls.child_by_field_name("name")
        cname_txt = text(cname, self.src) if cname is not None else ""
        bases = self._bases(cls)
        simple_bases = tuple(b.split(".")[-1] for b in bases)
        uses = self._attr_uses(attrs)
        partial = any(c.type == "modifier" and text(c, self.src) == "partial" for c in cls.children)
        if cname_txt:                              # what a derived controller in another file inherits
            self.out.publish(cname_txt, CsClass(tuple(prefixes), partial, uses, simple_bases))
            if cname_txt.endswith("Attribute"):
                self._route_attribute(cls, cname_txt, bases)
            if MODEL_CONVENTIONS & set(simple_bases) and "AttributeRouteModel" in text(cls, self.src):
                self.out.publish(cname_txt, RouteConvention())
            if any(FAST_ENDPOINT.match(seg) for b in bases for seg in b.split(".")):
                self.out.publish(cname_txt, FastBase(simple_bases))
            group = self._fe_group(cls, simple_bases)
            if group is not None:
                self.out.publish(cname_txt, group)
        controller = re.sub(r"Controller$", "", cname_txt)
        body = cls.child_by_field_name("body")
        if body is None or self._fast_endpoint(cls, body, bases):
            return
        names = {name for name, _, _ in attrs}
        segments = {seg for b in bases for seg in b.split(".")}
        is_controller = "NonController" not in names and (
            bool(prefixes) or cname_txt.endswith("Controller") or bool(names & {"ApiController", "Controller"})
            or any(b.split(".")[-1].endswith(("Controller", "ControllerBase")) for b in bases)
            or any(ENDPOINT_BASE.match(seg) for seg in segments))
        # not a controller by itself, but its routed actions are its derived controllers'
        # (`ProviderControllerBase<..> : RestControllerBase<..>`): published, never routes of its own
        base_only = not is_controller
        if base_only and not cname_txt:
            return
        prefix = prefixes[0] if prefixes else ""
        area = next((lit for name, lit, _ in attrs if name == "Area" and lit), "")
        if area and cname_txt:                      # `[Area]` is inherited: a derived controller's, if it has none
            self.out.publish(cname_txt, Area(area))
        # no [Route] of its own: what one of its routing attributes gives (`[V3ApiController]`), else its base classes' —
        # a `partial` half looks the class up first, its other halves' (`StoresController.Rates.cs`)
        inherit = not prefixes and (bool(bases) or bool(uses) or partial)
        route_bases = ((cname_txt,) if partial and not prefixes and cname_txt else ()) + simple_bases
        abstract = any(c.type == "modifier" and text(c, self.src) == "abstract" for c in cls.children)
        versions = self._declared_versions(attrs, "ApiVersion")
        odata = _is_odata(uses, simple_bases)
        own: set[str] = set()
        for m in body.children:
            if m.type != "method_declaration":
                continue
            mattrs = self._attrs(m)
            mname = m.child_by_field_name("name")
            hname = text(mname, self.src) if mname is not None else None
            plist = m.child_by_field_name("parameters")
            arity = sum(1 for c in plist.children if c.type == "parameter") if plist is not None else 0
            if any(name == "NonAction" for name, _, _ in mattrs):
                own.add((hname or "", arity))   # `[NonAction] override`: the base's action is not one here —
                if cname_txt:                   # nor in a class below this one
                    self.out.publish(cname_txt, NonAction(hname or "", arity))
                continue
            routes = [(CS_HTTP_ATTR[name], lit, a) for name, lit, a in mattrs if name in CS_HTTP_ATTR]
            extra = [lit for name, lit, _ in mattrs if name == "Route" and lit is not None]
            if not routes and extra and not self._attr_uses(mattrs):   # `[Route("docs")]` alone: any verb, once per route
                routes = [("ANY", lit, a) for name, lit, a in mattrs if name == "Route" and lit is not None]
            hid = next((s.id for s in self.symbols_by_name.get(hname or "", []) if s.kind == "method"), None)
            mversions = self._declared_versions(mattrs, "MapToApiVersion") or versions
            plain = not routes and not extra and self._plain_action(m)
            if not routes:
                action_uses = self._attr_uses(mattrs)
                if action_uses and cname_txt:   # maybe a routing attribute of the project (`[RestGetById]`): `compose` knows
                    first = next(a for name, _, a in mattrs if name == action_uses[0][0])
                    fact = AttrAction(self.endpoint_info(first, None, "/", "aspnet", hname, hid), action_uses,
                                      extra[0] if extra else "" if plain else None, hname or "", arity)
                    self.out.publish(cname_txt, fact)
                    if not abstract and not base_only:
                        wait = AttrActionRoute(fact, controller, tuple(prefixes), uses, route_bases, area, mversions)
                        self.out.pending.append(Pending(None, wait))
                    own.add((hname or "", arity))
                    continue
                if not plain or mname is None:
                    continue
                routes = [("ANY", None, mname)]     # a public method with no routing attribute: an action, any verb
            own.add((hname or "", arity))
            convention = self._odata_convention(m, hname or "", controller) if not extra else None
            for method, lit, a in routes:
                tmpl = lit if lit is not None else (extra[0] if extra else "")
                if not tmpl and convention is not None and odata and ODATA_VERBS.get(convention[0]) == method:
                    tmpl = convention[1]            # OData: `Put(int key, ..)` → `Categories({key})` under the route
                elif not tmpl and odata:
                    continue                        # OData routes an action without a template only by convention
                absolute = tmpl.startswith(("/", "~/"))
                if cname_txt:                   # what a derived controller in another file takes, under its own route
                    proto = self.endpoint_info(a, method, "/", "aspnet", hname, hid)
                    self.out.publish(cname_txt, Action(proto, tmpl, absolute, hname or "", arity))
                if abstract or base_only:
                    continue                    # not routable by itself: its actions live under each derived controller
                if not prefixes and not tmpl and not inherit:
                    continue                    # conventional routing ({controller}/{action}): no path of its own here
                full = tmpl if absolute else (prefix.rstrip("/") + "/" + tmpl).rstrip("/")
                for path in _version_paths(full, mversions):
                    path = _tokens(path.replace("~/", "/"), controller, hname or "", area)
                    ep = self.add_endpoint(a, method, path or "/", "aspnet", None, handler_name=hname, handler_id=hid)
                    if ep is not None and not area and AREA_TOKEN.search(path):   # the area of a base class
                        self.out.pending.append(Pending(ep, AreaRoute(route_bases)))
                    if ep is not None and API_VERSION.search(path):     # no version declared: the default one
                        names = tuple(m.group(1) for m in API_VERSION_NAME.finditer(path))
                        self.out.pending.append(Pending(ep, DefaultVersionRoute(names)))
                    if inherit and not absolute and ep is not None:
                        # `[HttpGet("")]`: an empty template written out is the app's root when no class above routes it
                        explicit = lit == ""
                        odata_tmpl = (convention[1] if convention is not None and ODATA_VERBS.get(convention[0]) == method
                                      else "") if not odata and not tmpl else None    # "": OData would not route it
                        self.out.pending.append(Pending(ep, InheritedRoute(route_bases, controller, hname or "",
                                                                           not tmpl and not explicit, area, uses, mversions,
                                                                           odata_tmpl)))
        if bases and not abstract and not base_only:   # the actions its base classes declare are routes of this controller too
            self.out.pending.append(Pending(None, InheritedActions(simple_bases, controller, tuple(prefixes), area,
                                                                   frozenset(own), uses, versions)))

    def _plain_action(self, m: Node) -> bool:
        """ASP.NET's test for an action with no routing attribute (`DefaultApplicationModelProvider.IsAction`): a public
        instance method, not abstract, not generic, not `Dispose` — a login controller's `Index` under `[Route(LoginPath)]`.
        An `override` takes the attributes of the method it overrides: the base's, left to it."""
        mods = {text(c, self.src) for c in m.children if c.type == "modifier"}
        name = m.child_by_field_name("name")
        return ("public" in mods and not mods & {"static", "abstract", "override"} and name is not None
                and text(name, self.src) != "Dispose" and not any(c.type == "type_parameter_list" for c in m.children))

    # -- the project's own routing attributes ------------------------------------------------------------
    def _route_attribute(self, cls: Node, name: str, bases: list[str]) -> None:
        """A routing attribute of the project — `[V3ApiController]` (`IRouteTemplateProvider`, `Template =
        $"api/v{version}/{resource}"` in its constructor), `[RestGetById]` (`IActionHttpMethodProvider` with
        `HttpMethods => new[] { "GET" }`), `[RestDeleteById]` (`: HttpDeleteAttribute`, `base("{id:int}")`), or
        `[VersionedApiRoute(x)]` (two levels over `RouteAttribute`). Published as a recipe over its constructor's
        parameters — what it hands its base, what it sets as `Template` — that `compose` fills with each use's arguments;
        the constants it names may live in another project. One deriving from another attribute of the project is
        resolved through it."""
        simple = [b.split(".")[-1].removesuffix("Attribute") for b in bases]
        framework = next((b for b in simple if b in ROUTE_ATTR_BASES), None)
        provider = bool(ROUTE_PROVIDERS & set(simple))
        parent = None if framework or provider else next((b for b in simple if b and not re.match(r"^I[A-Z]", b)), None)
        body = cls.child_by_field_name("body")
        if body is None or not (framework or provider or parent):
            return
        params: list[tuple[str, tuple | None]] = []
        env: dict[str, tuple] = {}
        assigned: dict[str, tuple] = {}
        base_args: tuple = ()
        ctor = next((m for m in body.children if m.type == "constructor_declaration"), None)
        if ctor is not None:
            plist = ctor.child_by_field_name("parameters")
            for prm in (c for c in plist.children if c.type == "parameter") if plist is not None else ():
                pname = prm.child_by_field_name("name")
                if pname is None:
                    continue
                kids = [c for c in prm.children if c.is_named]
                default = self._recipe(kids[-1], {}, cls) if any(c.type == "=" for c in prm.children) else None
                params.append((text(pname, self.src), default))
                env[text(pname, self.src)] = (("arg", text(pname, self.src)),)
            init = next((c for c in ctor.children if c.type == "constructor_initializer"), None)
            alist = next((c for c in init.children if c.type == "argument_list"), None) if init is not None else None
            if alist is not None:
                base_args = tuple(self._recipe(a, env, cls) for a in alist.children if a.type == "argument")
            block = ctor.child_by_field_name("body")
            for st in block.children if block is not None else ():
                e = st.named_children[0] if st.type == "expression_statement" and st.named_child_count else None
                left = e.child_by_field_name("left") if e is not None and e.type == "assignment_expression" else None
                if left is not None and left.type == "identifier":
                    r = self._recipe(e.child_by_field_name("right"), env, cls)
                    if r is not None:                    # `Version = version;` then `Template = $"v{Version}/.."`
                        env[text(left, self.src)] = assigned[text(left, self.src)] = r
        template, verbs = assigned.get("Template"), None
        for m in body.children:
            arrow = next((c for c in m.children if c.type == "arrow_expression_clause"), None) \
                if m.type == "property_declaration" else None
            pname = m.child_by_field_name("name") if arrow is not None else None
            expr = arrow.named_children[-1] if arrow is not None and arrow.named_child_count else None
            if pname is None or expr is None:
                continue
            if text(pname, self.src) == "Template":
                template = self._recipe(expr, env, cls)
            elif text(pname, self.src) == "HttpMethods":
                verbs = tuple(v for d in walk(expr) if d.type in STRING_NODES
                              and (v := unquote(text(d, self.src)).upper()) in HTTP_METHODS) or None
        if provider and template is None and verbs is None:
            return                                       # nothing this file can read
        self.out.publish(name.removesuffix("Attribute"), RouteAttr(framework, parent, tuple(params), base_args, template, verbs))

    def _attr_uses(self, attrs: list[tuple[str, str | None, Node]]) -> tuple:
        """The attributes that may be a routing attribute of the project (not the framework's), with their arguments as
        recipes (`_recipe`): (name without `Attribute`, positional, named by constructor parameter)."""
        out = []
        for name, _, a in attrs:
            simple = name.split(".")[-1].removesuffix("Attribute")
            if simple in FRAMEWORK_ATTRS or simple in CS_HTTP_ATTR:
                continue
            args = next((c for c in a.children if c.type == "attribute_argument_list"), None)
            pos, kw = [], []
            for arg in (c for c in args.children if c.type == "attribute_argument") if args is not None else ():
                kids = [c for c in arg.children if c.is_named]
                if not kids or kids[0].type == "name_equals":
                    continue                             # `Name = "x"`: a property, not the route's
                value = self._recipe(kids[-1], {})
                if kids[0].type == "name_colon":         # `resource: "x"`: a constructor parameter by name
                    label = next((c for c in kids[0].children if c.type == "identifier"), None)
                    kw.append((text(label, self.src) if label is not None else "", value))
                else:
                    pos.append(value)
            out.append((simple, tuple(pos), tuple(kw)))
        return tuple(out)

    def _recipe(self, n: Node | None, env: dict[str, tuple], cls: Node | None = None, _depth: int = 0) -> tuple | None:
        """A string expression of an attribute as parts `compose` fills: ("lit", s); ("arg", name) — a constructor
        parameter, or a property the constructor sets from one; ("const", "A.B.C") — a constant of another directory,
        read by its qualified name; ("trim", method, parts, chars) — `template.TrimStart('/')`, the characters written
        out or ("chars", "A.B") — a `char[]` field (`_char_array`). None for anything else (a call, a field this file
        cannot read)."""
        if n is None or _depth > 8:
            return None
        t = n.type
        if t in ("argument", "parenthesized_expression", "attribute_argument"):
            kids = [c for c in n.children if c.is_named and c.type not in ("name_colon", "name_equals")]
            return self._recipe(kids[-1], env, cls, _depth + 1) if kids else None
        if t in ("string_literal", "verbatim_string_literal", "raw_string_literal"):
            return (("lit", unquote(text(n, self.src))),)
        if t in ("integer_literal", "real_literal"):
            return (("lit", text(n, self.src)),)
        if t == "interpolated_string_expression":
            parts: list[tuple] = []
            for c in n.children:
                if c.type == "string_content":
                    r = self._content(text(c, self.src), env)
                    if r is None:
                        return None
                    parts.extend(r)
                elif c.type == "interpolation":
                    inner = next((k for k in c.children if k.is_named and k.type not in (
                        "interpolation_brace", "interpolation_alignment_clause", "interpolation_format_clause")), None)
                    r = self._recipe(inner, env, cls, _depth + 1)
                    if r is None:
                        return None
                    parts.extend(r)
            return tuple(parts)
        if t == "binary_expression":
            op = n.child_by_field_name("operator")
            left = self._recipe(n.child_by_field_name("left"), env, cls, _depth + 1)
            right = self._recipe(n.child_by_field_name("right"), env, cls, _depth + 1)
            ok = op is not None and text(op, self.src) == "+" and left is not None and right is not None
            return left + right if ok else None
        if t == "identifier":
            name = text(n, self.src)
            if name in env:
                return env[name]
            field = self._class_field(cls, name) if cls is not None else None
            if field is not None:                        # `string resource = CONTROLLER_RESOURCE`: the class's constant
                return self._recipe(field, {}, cls, _depth + 1)
            v = self._const_here(name)
            return (("lit", v),) if v is not None else None
        if t in ("member_access_expression", "qualified_name"):
            dotted = re.sub(r"\s+", "", text(n, self.src)).removeprefix("global::")
            v = self._const_here(dotted)
            return (("lit", v),) if v is not None else (("const", dotted),)
        if t == "invocation_expression":
            fn, args = n.child_by_field_name("function"), n.child_by_field_name("arguments")
            if fn is None or args is None:
                return None
            if text(fn, self.src) == "nameof":           # `nameof(id)` → `id`
                return (("lit", re.split(r"[.\s]", text(args, self.src).strip("() "))[-1]),)
            method = fn.child_by_field_name("name") if fn.type == "member_access_expression" else None
            if method is not None and text(method, self.src) in ("TrimStart", "TrimEnd", "Trim"):
                chars: str | tuple = ""
                trim_args = [a.named_children[-1] if a.named_child_count else a for a in args.children if a.type == "argument"]
                for e in trim_args:
                    if e.type in ("identifier", "member_access_expression") and len(trim_args) == 1:
                        chars = ("chars", re.sub(r"\s+", "", text(e, self.src)))   # `Constants.CharArrays.TildeForwardSlash`
                    elif e.type == "character_literal":
                        chars += text(e, self.src)[1:-1]
                    else:
                        return None
                inner = self._recipe(fn.child_by_field_name("expression"), env, cls, _depth + 1)
                return (("trim", text(method, self.src), inner, chars),) if inner is not None else None
        return None

    @staticmethod
    def _content(raw: str, env: dict[str, tuple]) -> list[tuple] | None:
        """The text of an interpolated string: `{{` and `}}` are braces. The grammar takes `$"{{{nameof(id)}:guid}}"` whole
        as text, so a lone `{..}` here is an interpolation the parser missed — `nameof(x)` or a constructor parameter;
        anything else is unknown."""
        parts: list[tuple] = []
        buf, i = "", 0
        while i < len(raw):
            if raw.startswith(("{{", "}}"), i):
                buf, i = buf + raw[i], i + 2
                continue
            if raw[i] == "{":
                j = raw.find("}", i)
                expr = raw[i + 1:j].split(":")[0].split(",")[0].strip() if j > i else ""
                m = re.fullmatch(r"nameof\(\s*([\w.]+)\s*\)", expr)
                if m is not None:
                    buf += m.group(1).split(".")[-1]
                elif expr in env:
                    parts += [("lit", buf), *env[expr]]
                    buf = ""
                else:
                    return None
                i = j + 1
                continue
            buf, i = buf + raw[i], i + 1
        return parts + [("lit", buf)]

    def _class_field(self, cls: Node, name: str) -> Node | None:
        """The value of a field or constant `name` the class declares (`const string CONTROLLER_RESOURCE = "[controller]"`)."""
        body = cls.child_by_field_name("body")
        for f in body.children if body is not None else ():
            if f.type != "field_declaration":
                continue
            for d in walk(f):
                kids = [c for c in d.children if c.is_named] if d.type == "variable_declarator" else []
                if len(kids) >= 2 and text(kids[0], self.src) == name:
                    v = kids[-1]
                    return v.named_children[-1] if v.type == "equals_value_clause" and v.named_child_count else v
        return None

    def _const_here(self, name: str) -> str | None:
        """A constant of this directory by its qualified name (`Paths.Root`, `Root`) — never by its last part alone, which
        another class may also name."""
        q = ".".join(name.split(".")[-2:])
        ctx = self.ctx
        if q in ctx.ambiguous:
            return None
        if q in ctx.route_consts or q in ctx.const_parts:
            return ctx.route_const(q)
        return ctx.segments.get(q) or ctx.relatives.get(q)

    def _odata_convention(self, m: Node, action: str, entity_set: str) -> tuple[str, str] | None:
        """OData's routing conventions for an action without a template (`Microsoft.AspNetCore.OData`): `Post` /
        `Get` on the entity set — the controller's name —, `Put` / `Patch` / `Delete` / `Get` with a `key` parameter
        on one entity, `Categories({key})`. (verb name, template), or None for an action they do not route."""
        verb = next((v for v in ODATA_VERBS if action in (v, v + entity_set)), None)
        if verb is None:
            return None
        params = m.child_by_field_name("parameters")
        names = [text(c.child_by_field_name("name"), self.src) for c in (params.children if params is not None else ())
                 if c.type == "parameter" and c.child_by_field_name("name") is not None]
        keyed = any(n == "key" or n.startswith("key") and n[3:4].isupper() for n in names)
        if verb in ("Put", "Patch", "Delete") and not keyed:
            return None
        return verb, entity_set + ("({key})" if keyed else "")

    def _default_api_version(self, n: Node) -> None:
        """Asp.Versioning's `options.DefaultApiVersion = new ApiVersion(1, 0)`: the version of a controller that
        declares none (`_RouteAttributes.default_version`)."""
        left, right = n.child_by_field_name("left"), n.child_by_field_name("right")
        if left is None or right is None or not text(left, self.src).endswith("DefaultApiVersion") \
                or right.type != "object_creation_expression" or not re.match(r"^new\s+ApiVersion\b", text(right, self.src)):
            return
        args = right.child_by_field_name("arguments")
        vals = [a.named_children[-1] for a in (args.children if args is not None else ()) if a.type == "argument" and a.named_child_count]
        lits = [unquote(text(v, self.src)) if v.type == "string_literal" else text(v, self.src) for v in vals
                if v.type in ("string_literal", "integer_literal", "real_literal")]
        if lits and len(lits) == len(vals):
            self.out.publish("", DefaultApiVersion(_version_text(".".join(lits[:2]))))

    def _char_array(self, n: Node) -> None:
        """`static readonly char[] TildeForwardSlash = { '~', '/' };`: the characters a route's `TrimStart(..)` may name
        (`_recipe`), known by `Class.Field`."""
        decl = next((c for c in n.children if c.type == "variable_declaration"), None)
        typ = decl.child_by_field_name("type") if decl is not None else None
        owner = owner_class(n, self.src)
        if typ is None or owner is None or re.sub(r"\s+", "", text(typ, self.src)) != "char[]":
            return
        for d in (c for c in decl.children if c.type == "variable_declarator"):
            kids = [c for c in d.children if c.is_named]
            nodes = list(walk(kids[-1])) if len(kids) >= 2 else []
            chars = [text(c, self.src)[1:-1] for c in nodes if c.type == "character_literal"]
            if chars and not any(c.startswith("\\") for c in chars) and not any(
                    c.type in STRING_NODES or c.type in ("identifier", "invocation_expression", "member_access_expression")
                    for c in nodes):
                self.out.publish(f"{owner}.{text(kids[0], self.src)}", CharArray("".join(chars)))

    def _route_convention_use(self, n: Node) -> None:
        """`options.Conventions.Add(new UmbracoBackofficeToken(Constants.Web.AttributeRouting.BackOfficeToken,
        backofficePath))`: a model convention registered with what it is given, as recipes (`_recipe`, a local read where
        it is declared above). `compose` takes one argument as a route token and the other as its value when the class
        rewrites attribute routes (`RouteConvention`)."""
        fn, args = n.child_by_field_name("function"), n.child_by_field_name("arguments")
        if fn is None or args is None or fn.type != "member_access_expression":
            return
        name, recv = fn.child_by_field_name("name"), fn.child_by_field_name("expression")
        if name is None or recv is None or text(name, self.src) not in ("Add", "Insert") \
                or not text(recv, self.src).endswith("Conventions"):
            return
        new = next((e for a in args.children if a.type == "argument" and a.named_child_count
                    and (e := a.named_children[-1]).type == "object_creation_expression"), None)
        typ = new.child_by_field_name("type") if new is not None else None
        cargs = new.child_by_field_name("arguments") if new is not None else None
        if typ is None or cargs is None:
            return
        env = self._locals(n)
        recipes = tuple(self._recipe(a, env) for a in cargs.children if a.type == "argument")
        self.out.publish(re.sub(r"<.*", "", text(typ, self.src)).split(".")[-1], ConventionUse(recipes))

    def _locals(self, at: Node) -> dict[str, tuple]:
        """The locals declared above `at` in the method around it — or in the file's top-level statements —, as recipes;
        a name declared twice there gives nothing."""
        scope = at.parent
        while scope is not None and scope.type not in ("method_declaration", "constructor_declaration", "local_function_statement"):
            scope = scope.parent
        env: dict[str, tuple] = {}
        declared: set[str] = set()
        for st in walk(scope if scope is not None else self.fx.tree.root_node):
            if st.type != "local_declaration_statement" or st.start_byte >= at.start_byte:
                continue
            for d in walk(st):
                kids = [c for c in d.children if c.is_named] if d.type == "variable_declarator" else []
                if len(kids) < 2:
                    continue
                nm, v = text(kids[0], self.src), kids[-1]
                v = v.named_children[-1] if v.type == "equals_value_clause" and v.named_child_count else v
                r = self._recipe(v, env) if nm not in declared else None
                env.pop(nm, None)
                if r is not None:
                    env[nm] = r
                declared.add(nm)
        return env

    def _declared_versions(self, attrs: list[tuple[str, str | None, Node]], kind: str) -> tuple[str, ...]:
        """Asp.Versioning: the versions `[ApiVersion("1.0")]` (on a controller) or `[MapToApiVersion("1.1")]` (on an
        action) declare, as the URL writes them (`_version_text`)."""
        out = []
        for name, _, a in attrs:
            if name.split(".")[-1].removesuffix("Attribute") != kind:
                continue
            args = next((c for c in a.children if c.type == "attribute_argument_list"), None)
            vals = [c.named_children[-1] for c in (args.children if args is not None else ())
                    if c.type == "attribute_argument" and c.named_child_count and c.named_children[0].type != "name_equals"]
            lits = [unquote(text(v, self.src)) if v.type == "string_literal" else text(v, self.src) for v in vals
                    if v.type in ("string_literal", "integer_literal", "real_literal")]
            if lits:
                numeric = all(v.type != "string_literal" for v in vals[:2])
                out.append(".".join(lits[:2]) if numeric and len(lits) > 1 else lits[0])
        return tuple(dict.fromkeys(_version_text(v) for v in out))

    def _fast_endpoint(self, cls: Node, body: Node, bases: list[str]) -> bool:
        """FastEndpoints: a class deriving from `Endpoint<...>` (`EndpointWithoutRequest`, `Ep.Req<..>.Res<..>`) — or
        overriding `Configure()` under a base of the project, which `compose` follows up to one over FastEndpoints'
        (`AppEndpoint<..>`) — that declares its routes in `Configure()`: `Get("/x")`, `Post(CreateRequest.Route)`,
        `Routes("/x")` with `Verbs(Http.POST)` in either order; the handler is its `HandleAsync`/`ExecuteAsync`.
        `RoutePrefixOverride(..)` takes the place of the global prefix (`_compose_fast_endpoints`)."""
        direct = any(FAST_ENDPOINT.match(seg) for b in bases for seg in b.split("."))
        methods = {text(m.child_by_field_name("name"), self.src): m for m in body.children
                   if m.type == "method_declaration" and m.child_by_field_name("name") is not None}
        configure = methods.get("Configure")
        if configure is None or not direct and not (
                bases and any(c.type == "modifier" and text(c, self.src) == "override" for c in configure.children)):
            return False
        hname = next((n for n in ("HandleAsync", "ExecuteAsync") if n in methods), None)
        first, last = cls.start_point[0] + 1, cls.end_point[0] + 1
        hid = next((s.id for s in self.symbols_by_name.get(hname or "", [])
                    if s.kind == "method" and first <= s.line_start <= last), None)
        verbs: list[str] = []
        routes: list[tuple[Node, str, str]] = []
        routed: list[tuple[Node, str]] = []
        override: tuple | None = None
        groups: list[tuple[int, str]] = []
        for d in walk(configure):
            kids = [c for c in d.children if c.is_named] if d.type == "invocation_expression" else []
            if len(kids) == 2 and kids[0].type == "generic_name" and kids[1].type == "argument_list" \
                    and not kids[1].named_child_count and text(kids[0].named_children[0], self.src) == "Group":
                targs = next((c for c in kids[0].named_children if c.type == "type_argument_list"), None)
                if targs is not None and targs.named_child_count == 1:     # `Group<Administration>()`
                    groups.append((d.start_byte, re.sub(r"<.*", "", text(targs.named_children[0], self.src)).split(".")[-1]))
                continue
            if len(kids) < 2 or kids[0].type != "identifier" or kids[-1].type != "argument_list":
                continue                        # only the endpoint's own calls: `Get(...)`, not `s.Get(...)`
            name = text(kids[0], self.src)
            args = [self._unwrap_arg(c) for c in kids[-1].children if c.is_named]
            if name == "Verbs":                 # `Http.POST`, `FastEndpoints.Http.POST`, "POST"
                verbs += [v for a in args if (v := unquote(text(a, self.src)).split(".")[-1].upper()) in HTTP_METHODS]
            elif name == "RoutePrefixOverride":
                override = self._recipe(args[0], {}) if args else None
                override = override if override is not None else (("unknown",),)
            elif name == "Routes":
                routed += [(d, p) for a in args if (p := self._fe_route(a)) is not None]
            elif name in FE_VERBS:
                routes += [(d, FE_VERBS[name], p) for a in args if (p := self._fe_route(a)) is not None]
        routes += [(d, verb, p) for d, p in routed for verb in verbs]
        if not direct and not routes:
            return False
        eps = [self.endpoint_info(d, verb, p, "fastendpoints", hname, hid) for d, verb, p in routes]
        if direct:
            self.out.endpoints.extend(eps)
        else:                                   # its routes once a base of the project reaches FastEndpoints'
            self.out.pending.append(Pending(None, FastEndpointRoutes(tuple(b.split(".")[-1] for b in bases), tuple(eps))))
        for ep in eps if override is not None else ():
            self.out.pending.append(Pending(ep, FePrefixOverride(override)))
        for ep, (d, _, _) in zip(eps, routes):  # a group takes the routes declared before it: FastEndpoints throws if none is
            names = tuple(g for at, g in groups if at > d.start_byte)
            if names:
                self.out.pending.append(Pending(ep, FeGroupRoute(names)))
        return True

    def _fe_route(self, a: Node) -> str | None:
        """A route FastEndpoints declares: what `path_of` reads (`Post(CreateRequest.Route)`, `Routes("x/y")`), or a
        literal template of one segment — the framework joins every route under its prefix and group (`Get("users")`)."""
        p = self.path_of(a, lenient=True)
        if p is not None or a.type not in STRING_NODES or has_interpolation(a):
            return p
        lit = unquote(text(a, self.src)).strip().lstrip("/")
        return "/" + lit if lit and PATH_LITERAL.match("/" + mask_placeholders(lit)) else None

    def _fe_group(self, cls: Node, bases: tuple[str, ...]) -> FeGroup | None:
        """A FastEndpoints endpoint group: a class under `Group`, or `SubGroup<TParent>`, whose constructor calls
        `Configure("admin", ep => ..)`. Its prefix as a recipe (None: one this file cannot read) and its parent's name —
        `Group<T>()` puts the group's prefix, then the parent's, before the endpoint's routes."""
        if "Group" not in bases and "SubGroup" not in bases:
            return None
        parent = None
        if "SubGroup" in bases:
            bl = next((c for c in cls.children if c.type == "base_list"), None)
            m = re.search(r"\bSubGroup\s*<\s*([\w.]+)\s*>", text(bl, self.src)) if bl is not None else None
            if m is None:
                return None
            parent = m.group(1).split(".")[-1]
        body = cls.child_by_field_name("body")
        for ctor in (c for c in body.children if c.type == "constructor_declaration") if body is not None else ():
            for d in walk(ctor):
                fn = d.child_by_field_name("function") if d.type == "invocation_expression" else None
                args = d.child_by_field_name("arguments") if fn is not None else None
                if args is not None and fn.type == "identifier" and text(fn, self.src) == "Configure":
                    vals = [c for c in args.children if c.is_named]
                    if len(vals) == 2:
                        return FeGroup(self._recipe(vals[0], {}, cls), parent)
        return None

    def _fe_route_prefix(self, n: Node) -> None:
        """FastEndpoints' global `config.Endpoints.RoutePrefix = "api"`, set where the app maps its endpoints
        (`UseFastEndpoints(c => ..)`): a literal or a constant, or a parameter of the method around it — what each call
        of that method in this file passes, the declared default of a parameter the caller passes on
        (`MapWorkflowsApi(.., string routePrefix = "app/api")`). A value a host passes from configuration is not read."""
        left, right = n.child_by_field_name("left"), n.child_by_field_name("right")
        if left is None or right is None or not re.sub(r"\s+", "", text(left, self.src)).endswith("Endpoints.RoutePrefix"):
            return
        values = self._param_values(right, n)
        for r in values if values else (None,):
            self.out.publish("", FePrefix(r))           # None: a value this file cannot read

    def _param_values(self, expr: Node, at: Node) -> set[tuple] | None:
        """The values `expr` may hold, as recipes: its own, or — a parameter of the method around `at` — what each call
        of that method in this file passes there, a parameter's default where nothing (or the caller's own parameter,
        with a default) is passed. None when one of them is unknown."""
        method = self._method_of(at)
        params = self._params(method) if method is not None else []
        index = next((i for i, (name, _, _) in enumerate(params) if expr.type == "identifier" and name == text(expr, self.src)), None)
        if index is None:
            r = self._recipe(expr, {})
            return {r} if r is not None else None
        mname = text(method.child_by_field_name("name"), self.src)
        out: set[tuple] = set()
        calls = [c for c in walk(self.fx.tree.root_node) if c.type == "invocation_expression"
                 and (fn := c.child_by_field_name("function")) is not None
                 and text(fn.child_by_field_name("name") if fn.type == "member_access_expression" else fn, self.src) == mname]
        for c in calls or (None,):
            arg = None
            if c is not None:
                fn = c.child_by_field_name("function")
                args = [a for a in c.child_by_field_name("arguments").children if a.type == "argument"]
                shift = 1 if params[0][2] and fn.type == "member_access_expression" else 0   # `x.M(a)`: x is `this`
                named = next((a for a in args if a.named_child_count > 1 and a.named_children[0].type == "name_colon"
                              and text(a.named_children[0], self.src).rstrip(": ") == params[index][0]), None)
                arg = named if named is not None else args[index - shift] if 0 <= index - shift < len(args) else None
            if arg is None:                     # not passed: the parameter's default
                r = self._recipe(params[index][1], {}) if params[index][1] is not None else None
            else:
                e = arg.named_children[-1] if arg.named_child_count else arg
                caller = self._method_of(c)
                passed_on = next((p for p in (self._params(caller) if caller is not None else [])
                                  if e.type == "identifier" and p[0] == text(e, self.src)), None)
                if passed_on is not None:       # the caller's own parameter: its default
                    r = self._recipe(passed_on[1], {}) if passed_on[1] is not None else None
                else:
                    r = self._recipe(e, {})
            if r is None:
                return None
            out.add(r)
        return out

    @staticmethod
    def _method_of(n: Node) -> Node | None:
        """The method around `n`, through its lambdas."""
        p = n.parent
        while p is not None and p.type not in ("method_declaration", "local_function_statement", "constructor_declaration"):
            p = p.parent
        return p

    def _params(self, method: Node) -> list[tuple[str, Node | None, bool]]:
        """(name, default value or None, `this`) for each parameter of `method`."""
        plist = method.child_by_field_name("parameters")
        out = []
        for prm in (c for c in plist.children if c.type == "parameter") if plist is not None else ():
            name = prm.child_by_field_name("name")
            eq = next((c for c in prm.children if c.type == "equals_value_clause"), None)
            default = eq.named_children[-1] if eq is not None and eq.named_child_count else \
                [c for c in prm.children if c.is_named][-1] if any(c.type == "=" for c in prm.children) else None
            this = any(c.type == "modifier" and text(c, self.src) == "this" or c.type == "parameter_modifier"
                       and text(c, self.src) == "this" for c in prm.children)
            out.append((text(name, self.src) if name is not None else "", default, this))
        return out

    @classmethod
    def compose(cls, out: HttpResult, repo: RepoInfo, view=None) -> None:
        """What crosses files in C#: calls to the repo's own client wrappers (`_compose_wrapped_calls`); the routing
        attributes of the project (`_RouteAttributes`), on a controller or an action; and the route a controller
        without a `[Route]` of its own takes from its base classes — their `[Route("[controller]")]`, or what a routing
        attribute of theirs gives —, walking up while a base has neither: a base is found by name in the repo, and
        two classes with that name (not `partial` halves of one) give nothing. An action with no template is a route
        only under that prefix. Last, a route token of the project takes its value (`_compose_route_tokens`)."""
        cls._compose_wrapped_calls(out)
        classes = out.facts_of(CsClass)
        attrs = _RouteAttributes(out.facts_of(RouteAttr), view,
                                 [v.version for v in out.facts_of(DefaultApiVersion).get("", ())],
                                 {k: [c.chars for c in v] for k, v in out.facts_of(CharArray).items()})
        areas = out.facts_of(Area)
        plan = {}
        for p in out.waiting(InheritedRoute):
            w, root = p.wait, p.wait.root
            area = w.area or _area_of(classes, areas, w.bases)
            route = attrs.route(w.uses)
            route = route if route is not None else _inherited_route(classes, w.bases, attrs)
            if route is not None and w.odata_template is not None and _odata_base(classes, w.bases):
                if not w.odata_template:
                    plan[id(p.item)] = []                          # OData routes an untemplated action only by convention
                    continue
                route = route.rstrip("/") + "/" + w.odata_template  # the OData convention, the base being an ODataController
                root = False
            if route is not None:
                plan[id(p.item)] = [rebased(repo, p.item, _tokens(r, w.controller, w.action, area))
                                    for r in _version_paths(route, w.versions or attrs.default_version)]
            elif root:
                plan[id(p.item)] = []
        replace_endpoints(out, plan)
        for p in out.waiting(AttrActionRoute):
            w, act = p.wait, p.wait.action
            area = w.area or _area_of(classes, areas, w.bases)
            route = w.routes[0] if w.routes else attrs.route(w.uses)
            route = route if route is not None else _inherited_route(classes, w.bases, attrs)
            _attr_action(out, repo, attrs, act.proto, act.uses, act.extra, route, w.controller, act.name, area,
                         w.versions or attrs.default_version)
        cls._compose_inherited_actions(out, repo, classes, attrs)
        plan = {}
        for p in out.waiting(DefaultVersionRoute) if attrs.default_version else ():   # no version declared
            path = p.item.path
            for name in p.wait.names:
                path = path.replace("{" + name + "}", attrs.default_version[0])
            plan[id(p.item)] = [replace(p.item, path=path, id=ids.http_endpoint(repo.tenant, repo.name, p.item.method,
                                                                                  path_key(path)))]
        replace_endpoints(out, plan)
        # a route of its own whose `[Area]` is a base class's — by its line, which the passes above keep
        at = {(p.item.file_id, p.item.line): area for p in out.waiting(AreaRoute)
              if (area := _area_of(classes, areas, p.wait.bases))}
        plan = {}
        for ep in out.endpoints:
            area = at.get((ep.file_id, ep.line)) if ep.framework == "aspnet" else None
            if area and AREA_TOKEN.search(ep.path):
                path = AREA_TOKEN.sub(lambda _: area, ep.path)
                plan[id(ep)] = [replace(ep, path=path, id=ids.http_endpoint(repo.tenant, repo.name, ep.method, path_key(path)))]
        replace_endpoints(out, plan)
        cls._compose_route_tokens(out, repo, attrs)
        cls._compose_fast_endpoints(out, repo, classes, attrs)

    @staticmethod
    def _compose_fast_endpoints(out: HttpResult, repo: RepoInfo, classes: dict[str, list], attrs: "_RouteAttributes") -> None:
        """FastEndpoints across files: an endpoint under a base of the project takes its routes when the walk up its bases
        reaches one over FastEndpoints' (`FastBase`) — a name several classes share counts when each of them does
        (`AppEndpoint<TRequest>`, `<TRequest, TResponse>`, ..). Then the prefix of its group (`FeGroup`), and
        before it the global `RoutePrefix`, when the repo sets one value (`FePrefix`), unless the route overrides it."""
        fast = out.facts_of(FastBase)
        for p in out.waiting(FastEndpointRoutes):
            if _reaches_fast(classes, fast, p.wait.bases):
                out.endpoints.extend(p.wait.endpoints)
        prefixes = {attrs.fill(f.prefix, {}) if f.prefix is not None else None for f in out.facts_of(FePrefix).get("", [])}
        prefix = prefixes.pop() if len(prefixes) == 1 else None
        overrides = {id(p.item): p.wait.prefix for p in out.waiting(FePrefixOverride)}
        grouped = {id(p.item): p.wait.groups for p in out.waiting(FeGroupRoute)}
        groups = out.facts_of(FeGroup)
        plan = {}
        for ep in out.endpoints:
            if ep.framework != "fastendpoints":
                continue
            own = attrs.fill(overrides[id(ep)], {}) if id(ep) in overrides else prefix
            group = _fe_group_prefix(groups, grouped[id(ep)], attrs) if id(ep) in grouped else None
            full = "/".join(s.strip("/") for s in (own, group) if s and s.strip("/"))
            if full:
                plan[id(ep)] = [rebased(repo, ep, "/" + full)]
        replace_endpoints(out, plan)

    @staticmethod
    def _compose_route_tokens(out: HttpResult, repo: RepoInfo, attrs: "_RouteAttributes") -> None:
        """A route token of the project — `[umbracoBackOffice]`, not one of the framework's — is the value the convention
        that rewrites the attribute routes (`RouteConvention`) is registered with: of the two arguments of
        `Conventions.Add(new T(token, value))` one is the token's name, the other a value the code fixes
        (`DefaultAppPath.TrimStart(TildeForwardSlash)`, `app`). One read from configuration, or two registrations
        with different values, leave the token as written."""
        routes = [ep for ep in out.endpoints if ep.framework == "aspnet" and "[" in ep.path]
        used = {m.group(1) for ep in routes for m in ROUTE_TOKEN.finditer(ep.path)} - FRAMEWORK_TOKENS
        if not used:
            return
        conventions = out.facts_of(RouteConvention)
        found: dict[str, set] = {}
        for tname, registrations in out.facts_of(ConventionUse).items():
            for use in registrations if tname in conventions else ():
                values = [attrs.fill(r, {}) for r in use.args]
                hits = [i for i, v in enumerate(values) if v is not None and v.removeprefix("[").removesuffix("]") in used]
                if len(values) != 2 or len(hits) != 1:
                    continue
                token, value = values[hits[0]].removeprefix("[").removesuffix("]"), values[1 - hits[0]]
                found.setdefault(token, set()).add(value if value is not None and TOKEN_VALUE.match(value) else None)
        tokens = {t: v.pop() for t, v in found.items() if len(v) == 1 and None not in v}
        plan = {}
        for ep in routes:
            path = ROUTE_TOKEN.sub(lambda m: tokens.get(m.group(1), m.group(0)), ep.path)
            if path != ep.path:
                path = normalize_path(path)
                plan[id(ep)] = [replace(ep, path=path, id=ids.http_endpoint(repo.tenant, repo.name, ep.method, path_key(path)))]
        replace_endpoints(out, plan)

    @staticmethod
    def _compose_inherited_actions(out: HttpResult, repo: RepoInfo, classes: dict[str, list], attrs: "_RouteAttributes") -> None:
        """`EmailTemplatesController : ChannelTemplatesController<T, TDto>` with `[Route("api/apps/{appId}/email-templates")]`
        and no action of its own: the actions its base classes declare (found by name, as the `[Route]`, nearest first)
        are its routes, under its route — or the one it inherits — with `[controller]` its name:
        `MovieController : RestControllerBase<..> : RestController<T>` takes `RestController`'s `[RestGetById]`.
        An action it — or a nearer base — redeclares is that one's; a base two classes share the name of stops the walk."""
        actions, attr_actions, non_actions = out.facts_of(Action), out.facts_of(AttrAction), out.facts_of(NonAction)
        for p in out.waiting(InheritedActions):
            w = p.wait
            bases, controller = w.bases, w.controller
            area = w.area or _area_of(classes, out.facts_of(Area), bases)
            versions = w.versions or attrs.default_version
            route = w.routes[0] if w.routes else attrs.route(w.uses)
            route = route if route is not None else _inherited_route(classes, bases, attrs)
            if route is None:
                continue
            seen = set(w.own)                        # (name, arity): an overload is another action
            for base in _ancestors(classes, bases):
                seen |= {(n.name, n.arity) for n in non_actions.get(base, ())}   # `[NonAction] override ..`
                here: set[tuple[str, int]] = set()
                for a in actions.get(base, ()):
                    if (a.name, a.arity) in seen:
                        continue
                    here.add((a.name, a.arity))
                    full = a.template if a.absolute else (route.rstrip("/") + "/" + a.template).rstrip("/")
                    for v in _version_paths(full, versions):
                        path = normalize_path(_tokens(v.replace("~/", "/"), controller, a.name, area) or "/")
                        out.endpoints.append(replace(a.proto, path=path, raw_pattern=a.template or "/",
                                                     id=ids.http_endpoint(repo.tenant, repo.name, a.proto.method,
                                                                          path_key(path))))
                for a in attr_actions.get(base, ()):
                    if (a.name, a.arity) not in seen and _attr_action(out, repo, attrs, a.proto, a.uses, a.extra, route,
                                                                      controller, a.name, area, versions):
                        here.add((a.name, a.arity))
                seen |= here

    @staticmethod
    def _compose_wrapped_calls(out: HttpResult) -> None:
        """A call to a client wrapper (`HttpService.HttpGet(uri)`, found by the receiver's declared type) is an
        outbound call: the wrapper's verb, its text around the argument that is the path. A name two wrappers of that
        type define differently (overloads) gives nothing."""
        wrappers = out.facts_of(ClientWrapper)
        for p in out.waiting(ClientWrapperCall):
            via = f"{p.wait.receiver_type}.{p.wait.name}"
            shapes = set(wrappers.get(via, ()))
            if len(shapes) != 1:
                continue
            w, args = next(iter(shapes)), p.wait.args
            found = wrapped_path(w.before, args[w.index] if w.index < len(args) else None, w.after)
            if found is not None:
                out.calls.append(replace(p.item, method=w.verb, path=found[1], raw_path=found[0], via=via[-60:]))

    def _refit(self, iface: Node) -> None:
        body = iface.child_by_field_name("body")
        if body is None:
            return
        for m in body.children:
            if m.type != "method_declaration":
                continue
            for name, lit, a in self._attrs(m):
                if name in ("Get", "Post", "Put", "Patch", "Delete", "Head", "Options") and lit is not None:
                    self.add_call(a, VERB_BY_NAME[name], lit, "refit")

    def _maybe_group(self, n: Node) -> None:
        kids = [c for c in n.children if c.is_named]
        if len(kids) < 2 or kids[0].type != "identifier":
            return
        val = kids[-1]
        if val.type == "equals_value_clause":
            inner = [c for c in val.children if c.is_named]
            val = inner[-1] if inner else val
        if val.type != "invocation_expression":
            return
        txt = text(val, self.src)
        if ".MapGroup" in txt:
            grp = None
            for d in walk(val):
                if d.type != "invocation_expression":
                    continue
                callee = next((c for c in d.children if c.is_named), None)
                if callee is not None and callee.type != "argument_list" and text(callee, self.src).endswith("MapGroup"):
                    grp = d                    # pre-order: the deepest (innermost) MapGroup wins
            if grp is not None:
                args = next((c for c in grp.children if c.type == "argument_list"), None)
                arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named] if args else []
                fn_text = text(grp, self.src).split("(")[0]
                self._record_group([text(kids[0], self.src)], grp, fn_text, arg_nodes)
        elif re.search(r"\b(WebApplication|CreateBuilder|Build)\s*\(", txt):
            self.router_vars.add(text(kids[0], self.src))
            self.mark_app(text(kids[0], self.src), n)

    def _invocation(self, n: Node) -> None:
        kids = [c for c in n.children if c.is_named]
        if len(kids) < 2 or kids[-1].type != "argument_list":
            return
        fn, args = kids[0], kids[-1]
        callee = self.callee_of(fn)
        while "<" in callee and re.search(r"<[^<>]*>", callee):   # GetFromJsonAsync<T>, GetFromJsonAsync<List<T>>
            callee = re.sub(r"<[^<>]*>", "", callee)
        name, _, recv_last = split_callee(callee)
        arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named]
        if self.convention_call(n, name, recv_last, callee, arg_nodes):
            return
        # Flurl: the *receiver* is the URL — "api/x".GetJsonAsync(), url.AppendPathSegment("orders").PostJsonAsync(body)
        if name in FLURL_VERBS and fn.type == "member_access_expression":
            kids_fn = [c for c in fn.children if c.is_named]
            recv_node = kids_fn[0] if kids_fn else None
            p = self._flurl_path(recv_node) if recv_node is not None else None
            if p is not None:
                self.add_call(n, FLURL_VERBS[name], p, "flurl." + name)
                return
        if not arg_nodes:
            return
        if name in CS_MAP and len(arg_nodes) >= 2:
            p = self.route_path(arg_nodes[0], recv_last, n)
            if p is not None and (self.is_handler_like(arg_nodes[-1]) or True):
                method = CS_MAP[name]
                if name == "MapMethods":
                    method = self.method_from_args(arg_nodes[1:2]) or "ANY"
                # the evidence is where `MapGet` is written: code the parser could not read folds into the receiver
                # (a Program.cs with an `else if` without a body 600 lines above)
                at = fn.child_by_field_name("name") if fn.type == "member_access_expression" else None
                self.add_endpoint(at or n, method or "ANY", p, "aspnet-minimal", arg_nodes[-1], router=recv_last)
                return
        # with no receiver, the call is the type's own method: never a client's
        if name in OUTBOUND and name.endswith("Async") and fn.type not in ("identifier", "generic_name"):
            if name == "SendAsync" and arg_nodes and arg_nodes[0].type == "identifier":
                val = self.resolve_local(arg_nodes[0])
                if val is not None and val.type == "object_creation_expression" and "HttpRequestMessage" in text(val, self.src):
                    return                                  # recorded at `new HttpRequestMessage(...)`
            method = OUTBOUND.get(name) or self.method_from_args(arg_nodes)
            for a in arg_nodes:
                p = self.path_of(a, lenient=True)
                if p is not None:
                    self.add_call(n, method, p, callee)
                    return
            self._wrapper(n, method, arg_nodes)
            return
        self._wrapped_call(n, fn, name, arg_nodes)

    # -- NSwag-generated clients ----------------------------------------------------------------------
    def _nswag_operation(self, m: Node) -> None:
        """One operation of an NSwag client: the path template from `// Operation Path: "api/x/{id}"` (v14), else from
        the `urlBuilder_.Append(..)` literals (v13: `Append("api/x/{id}")` + `Replace("{id}", ..)`), the base URL before
        it and the query after `?` left out; the verb from `request_.Method = new HttpMethod("GET")`."""
        body = m.child_by_field_name("body")
        if body is None:
            return
        verb = op_path = None
        appends: list[Node] = []
        for d in walk(body):
            if d.type == "comment" and op_path is None:
                found = re.match(r'//\s*Operation Path:\s*"([^"]*)"', text(d, self.src))
                op_path = found.group(1) if found else None
            elif d.type == "assignment_expression":
                left, right = d.child_by_field_name("left"), d.child_by_field_name("right")
                if left is not None and right is not None and text(left, self.src) == "request_.Method":
                    verb = (first_string(right, self.src) or "").upper() or None
            elif d.type == "invocation_expression":
                kids = [c for c in d.children if c.is_named]
                callee = self.callee_of(kids[0]) if kids else ""
                if callee.startswith("urlBuilder_.") and callee.endswith(".Append") and kids[-1].type == "argument_list":
                    arg = next((self._unwrap_arg(c) for c in kids[-1].children if c.is_named), None)
                    if arg is not None:
                        appends.append(arg)
        if not appends:
            return
        appends.sort(key=lambda a: a.start_byte)
        path = op_path
        if path is None:
            parts: list[str] = []
            for a in appends:
                lit = unquote(text(a, self.src)) if a.type in ("string_literal", "verbatim_string_literal", "character_literal") else None
                if lit is None:
                    if parts:                                   # before the path: the base URL
                        parts.append("{param}")
                    continue
                parts.append(lit.split("?", 1)[0])
                if "?" in lit:
                    break
            path = "".join(parts)
        if verb in HTTP_METHODS and path and valid_path("/" + path.lstrip("/")):
            self.add_call(next((a for a in appends if a.type == "string_literal"), appends[0]), verb,
                          "/" + path.lstrip("/"), "generated-client")

    # -- the repo's own client wrappers: `HttpService.HttpGet<T>(string uri)` and the calls to it --------------
    def _wrapper(self, call: Node, method: str | None, arg_nodes: list[Node]) -> None:
        """`_http.GetAsync($"{_apiUrl}{uri}")` inside `HttpGet<T>(string uri)`: the path is the caller's. Publish the
        method as a client wrapper — which parameter is the path, the verb, what goes around it — under its class and
        the class's bases (a field is often typed by the interface)."""
        m = enclosing_function(call)
        if m is None or m.type != "method_declaration" or m.child_by_field_name("name") is None:
            return
        pl = m.child_by_field_name("parameters")
        params = [text(p.child_by_field_name("name"), self.src) for p in (pl.children if pl is not None else ())
                  if p.type == "parameter" and p.child_by_field_name("name") is not None]
        shape = next((sh for a in arg_nodes if (sh := param_shape(self, a, params)) is not None), None)
        cls = m.parent
        while cls is not None and cls.type not in CLASS_NODES:
            cls = cls.parent
        if shape is None or cls is None or cls.child_by_field_name("name") is None:
            return
        mname = text(m.child_by_field_name("name"), self.src)
        for owner in [text(cls.child_by_field_name("name"), self.src)] + [b.split(".")[-1] for b in self._bases(cls)]:
            self.out.publish(f"{owner}.{mname}", ClientWrapper(*shape, (method or "ANY").upper()))

    def _wrapped_call(self, n: Node, fn: Node, name: str, arg_nodes: list[Node]) -> None:
        """`_httpService.HttpGet<T>("catalog-items")`: a call on a receiver of a known type with a string argument
        waits for `compose` to find whether that type's method is a client wrapper (it may live in another file)."""
        recv = fn.child_by_field_name("expression") if fn.type == "member_access_expression" else None
        if recv is None or not arg_nodes:
            return
        args = tuple(self._literal(a) for a in arg_nodes)
        rtype = self._declared_type(recv, n) if any(args) else None
        if rtype:
            self.out.pending.append(Pending(self.call_info(n, None, "", name), ClientWrapperCall(rtype, name, args)))

    def _literal(self, a: Node) -> str | None:
        """Text of a string argument (a template with `{param}`), or of the local it is assigned to."""
        if a.type == "identifier":
            bound, val = self.scopes.binding(a)
            a = val if bound and val is not None else a
        if a.type not in STRING_NODES:
            return None
        return self._interpolated(a, True) if a.type == "interpolated_string_expression" or has_interpolation(a) \
            else unquote(text(a, self.src))

    def _declared_type(self, recv: Node, at: Node) -> str | None:
        """The simple name of the type the receiver's declaration gives it: the answer the resolver gets, with a
        method's result and the members after it read through the type service (a base's field, another part of a
        partial class, a field's field)."""
        found = receiver_type(at, recv, self.src)
        if found is None or not found[1] and not found[0].startswith(("call:", "name:")):
            return found[0].rpartition(".")[2] if found is not None else None
        view = self.ctx.view
        types = view.types.of("csharp") if view is not None and view.types is not None else None
        cur, name = start_of(types, self.fx.file.path, found[0])
        for member in found[1]:
            field = types.field(cur, member) if not isinstance(cur, Unknown) else cur
            if isinstance(field, Unknown):
                return None
            name, cur = field.written, field.type
        return name

    def _flurl_path(self, n: Node) -> str | None:
        """URL built by Flurl chaining: base.AppendPathSegment("orders").AppendPathSegment(id).SetQueryParam(...)."""
        segs: list[str] = []
        cur = n
        while cur is not None and cur.type == "invocation_expression":
            kids = [c for c in cur.children if c.is_named]
            if len(kids) < 2 or kids[0].type != "member_access_expression":
                break
            fk = [c for c in kids[0].children if c.is_named]
            mname = text(fk[-1], self.src) if fk else ""
            args = [self._unwrap_arg(c) for c in kids[1].children if c.is_named]
            if mname in ("AppendPathSegment", "AppendPathSegments", "Request"):
                for a in args:
                    lit = unquote(text(a, self.src)) if a.type in STRING_NODES else None
                    segs.insert(0, lit if lit else "{param}")
            elif mname in ("SetQueryParam", "SetQueryParams", "WithHeader", "WithHeaders", "WithOAuthBearerToken", "WithTimeout", "AllowAnyHttpStatus", "WithBasicAuth"):
                pass
            else:
                break
            cur = fk[0] if fk else None
        base = self.path_of(cur, lenient=True) if cur is not None else None
        if base is None and not segs:
            return None
        path = "/".join([base.strip("/")] if base else []) + ("/" + "/".join(segs) if segs else "")
        return ("/" + path.lstrip("/")) if path else None

    def _request_message(self, n: Node) -> None:
        """`new HttpRequestMessage(HttpMethod.Post, "api/x")` and RestSharp `new RestRequest("api/x", Method.Post)`."""
        head = text(n, self.src).split("(")[0]
        if "HttpRequestMessage" not in head and "RestRequest" not in head:
            return
        args = next((c for c in n.children if c.type == "argument_list"), None)
        arg_nodes = [self._unwrap_arg(c) for c in args.children if c.is_named] if args else []
        method = self.method_from_args(arg_nodes)
        if method is None:                                   # RestSharp: Method.Get / Method.Post
            for a in arg_nodes:
                m = re.match(r"^Method\.([A-Za-z]+)$", text(a, self.src))
                if m and m.group(1).upper() in HTTP_METHODS:
                    method = m.group(1).upper()
        via = "new HttpRequestMessage" if "HttpRequestMessage" in head else "new RestRequest"
        for a in arg_nodes:
            p = self.path_of(a, lenient=True)
            if p is not None:
                self.add_call(n, method, p, via)
                return


def _aspnet_template(t: str) -> str:
    """An ASP.NET route template's parameters as `{name}`: catch-all stars, constraints with arguments (a regex keeps its
    parentheses balanced and its braces doubled: `{**path:regex(^(?!(api|feed)/).*)}`), defaults and the
    optional `?` (`{id?}`, `{id:int?}`) go; `{{` / `}}` outside a parameter are literal braces and stay."""
    if "{" not in t:
        return t
    out, i = "", 0
    while i < len(t):
        if t.startswith(("{{", "}}"), i):
            out, i = out + t[i:i + 2], i + 2
            continue
        if t[i] != "{":
            out, i = out + t[i], i + 1
            continue
        j, depth = i + 1, 0
        while j < len(t):
            if t.startswith(("{{", "}}"), j):
                j += 2
                continue
            if t[j] == "(":
                depth += 1
            elif t[j] == ")":
                depth = max(depth - 1, 0)
            elif t[j] == "}" and depth == 0:
                break
            j += 1
        if j >= len(t):
            return out + t[i:]                         # not a parameter: left as written
        name = re.match(r"^\*{0,2}([A-Za-z_][\w.]*)", t[i + 1:j])
        out += "{" + name.group(1) + "}" if name else t[i:j + 1]
        i = j + 1
    return out


def _tokens(path: str, controller: str, action: str, area: str = "") -> str:
    """ASP.NET route tokens as the framework fills them — and as its OpenAPI and the clients generated from it write
    them: `[controller]` is the class name without `Controller`, `[action]` the method name without `Async`
    (`SuppressAsyncSuffixInActionNames`, on by default), `[area]` the controller's `[Area("..")]`. The parameters
    `{controller}`, `{area}`, `{action}` are reserved: the router fixes them to the same values. The framework
    matches without case; so does the linker for these routes."""
    path = re.sub(r"\[controller\]|\{controller\}", lambda _: controller, path, flags=re.I)
    if area:
        path = re.sub(r"\[area\]|\{area\}", lambda _: area, path, flags=re.I)
    return re.sub(r"\[action\]|\{action\}", lambda _: re.sub(r"Async$", "", action), path, flags=re.I)


def _inherited_route(classes: dict[str, list], bases: tuple[str, ...], attrs: "_RouteAttributes") -> str | None:
    """The route of the nearest base class of this repo that has one: its `[Route]`, or what one of its routing
    attributes gives (a `DataTypeControllerBase` carrying `[VersionedApiRoute(..)]`); None when a
    name on the way is ambiguous or no base has one."""
    for base in _ancestors(classes, bases):
        decls = classes[base]
        route = next((d.routes[0] for d in decls if d.routes), None)
        if route is None:
            route = next((r for d in decls if (r := attrs.route(d.uses)) is not None), None)
        if route is not None:
            return route
    return None


def _is_odata(uses: tuple, bases: tuple[str, ...]) -> bool:
    """A controller OData routes by convention: `[ODataRouteComponent]` on it, or `ODataController` among its bases."""
    return "ODataController" in bases or any(name == "ODataRouteComponent" for name, _, _ in uses)


def _odata_base(classes: dict[str, list], bases: tuple[str, ...]) -> bool:
    """`_is_odata` for one of the repo's classes above a controller (a `WebApiController<T>` carrying
    `[ODataRouteComponent("odata/v1")]`, over `AppODataController<T> : ODataController`)."""
    return any(_is_odata(d.uses, d.bases) for base in _ancestors(classes, bases) for d in classes[base])


def _ancestors(classes: dict[str, list], bases: tuple[str, ...], limit: int = 4) -> list[str]:
    """The repo's classes above a controller, nearest first, found by name; the walk stops at a name two classes (not
    `partial` halves of one) share, or at a base outside the repo."""
    out: list[str] = []
    level = bases
    while level and len(out) < limit:
        base = next((b for b in level if b in classes), None)
        if base is None or base in out or sum(1 for d in classes[base] if not d.partial) > 1:
            break
        out.append(base)
        level = tuple(b for d in classes[base] for b in d.bases)
    return out


def _area_of(classes: dict[str, list], areas: dict[str, list], bases: tuple[str, ...]) -> str:
    """The `[Area]` of the nearest base class of the repo that has one (`AreaAttribute` is inherited:
    `PaymentAdminController : AdminController`, `[Area("Admin")]`); "" when none has, or that class has two."""
    for base in _ancestors(classes, bases):
        found = {a.name for a in areas.get(base, ())}
        if found:
            return found.pop() if len(found) == 1 else ""
    return ""


def _fe_group_prefix(groups: dict[str, list], names: tuple[str, ...], attrs: "_RouteAttributes") -> str | None:
    """What the endpoint groups `names` (its `Group<T>()` calls, in order) put before its routes: each group's prefix,
    then its parent's (`SubGroup<TParent>`), each before what is there. None when a group is not the repo's one class of
    that name, or its prefix cannot be read — the route stays as written."""
    segments: list[str] = []
    for name in names:
        g, depth = name, 0
        while g is not None:
            decls = set(groups.get(g, ()))
            if len(decls) != 1 or depth > 5:
                return None
            group = decls.pop()
            recipe, g = group.prefix, group.parent
            value = attrs.fill(recipe, {}) if recipe is not None else None
            if value is None:
                return None
            segments.insert(0, value.strip("/"))
            depth += 1
    return "/".join(s for s in segments if s)


def _reaches_fast(classes: dict[str, list], fast: dict[str, list], bases: tuple[str, ...], _depth: int = 0) -> bool:
    """Some base, found by name in the repo, is over FastEndpoints' — each class of that name with bases, by its own
    bases (`FastBase`) or further up, up to four levels."""
    if _depth > 3:
        return False
    for b in bases:
        decls = [d for d in classes.get(b, ()) if d.bases]
        over = {f.bases for f in fast.get(b, ())}
        if decls and all(d.bases in over or _reaches_fast(classes, fast, d.bases, _depth + 1) for d in decls):
            return True
    return False


def _attr_action(out: HttpResult, repo: RepoInfo, attrs: "_RouteAttributes", proto, action_uses: tuple, extra: str,
                 route: str | None, controller: str, action: str, area: str, versions: tuple[str, ...]) -> bool:
    """An action routed by a routing attribute of the project (`[RestGetById]` → GET `{id:int}`), under `route`: one
    route per verb it gives. False when none of its attributes is one."""
    found = attrs.action(action_uses)
    if found is None:
        if extra is None:
            return False
        found = (("ANY",), extra)                    # `[Route("x")]` or none, its other attributes routing nothing: any verb
    verbs, tmpl = found
    tmpl = tmpl or extra
    absolute = tmpl.startswith(("/", "~/"))
    if route is None and not absolute and not tmpl:
        return False                                 # conventional routing: no path of its own
    full = tmpl if absolute else ((route or "").rstrip("/") + "/" + tmpl).rstrip("/")
    for v in _version_paths(full, versions):
        path = normalize_path(_tokens(v.replace("~/", "/"), controller, action, area) or "/")
        for verb in verbs:
            out.endpoints.append(replace(proto, method=verb, path=path, raw_pattern=tmpl or "/",
                                         id=ids.http_endpoint(repo.tenant, repo.name, verb, path_key(path))))
    return True


def _version_text(v: str) -> str:
    """Asp.Versioning's URL form of a version (its default `VVV`): `1.0` → `1`, `1.1` → `1.1`, `2.0-beta` → `2-beta`."""
    m = re.match(r"^(\d+)(?:\.(\d+))?(.*)$", v.strip())
    if m is None:
        return v
    major, minor, rest = m.groups()
    return major + (f".{minor}" if minor not in (None, "0") else "") + rest


def _version_paths(path: str, versions: tuple[str, ...]) -> list[str]:
    """`api/v{version:apiVersion}/x` once per version the controller or the action declares; as written when none is."""
    if not versions or not API_VERSION.search(path):
        return [path]
    return [API_VERSION.sub(lambda _: v, path) for v in versions]


class _RouteAttributes:
    """The project's routing attributes (`RouteAttr`), filled with a use's arguments. A constant a recipe names is
    read by its qualified name in any directory of the repo (`Constants.Web.ManagementApiPath` → `Web.ManagementApiPath`),
    and only when the repo gives it one value; two attributes with one name give nothing."""

    def __init__(self, facts: dict[str, list], view, default_versions: list | None = None,
                 chars: dict[str, list] | None = None) -> None:
        self.facts, self.view, self.chars = facts, view, chars or {}
        # Asp.Versioning: a controller with no `[ApiVersion]` is the default version — the repo's
        # `DefaultApiVersion` when it sets one, else the library's 1.0
        found = set(default_versions or ())
        self.default_version: tuple[str, ...] = (found.pop(),) if len(found) == 1 else ("1",) if not found else ()

    def const(self, dotted: str) -> str | None:
        if "." not in dotted or self.view is None:
            return None
        found = self.view.constant_values(".".join(dotted.split(".")[-2:]))
        return next(iter(found)) if len(found) == 1 else None

    def fill(self, recipe: tuple | None, values: dict[str, str | None]) -> str | None:
        if recipe is None:
            return None
        out = ""
        for part in recipe:
            if part[0] == "lit":
                v = part[1]
            elif part[0] == "arg":
                v = values.get(part[1])
            elif part[0] == "const":
                v = self.const(part[1])
            elif part[0] == "trim":
                v = self.fill(part[2], values)
                if isinstance(part[3], tuple):           # a `char[]` field, by `Class.Field`, one value in the repo
                    found = set(self.chars.get(".".join(part[3][1].split(".")[-2:]), ()))
                    if len(found) != 1:
                        return None
                    chars = found.pop()
                else:
                    chars = part[3] or None
                v = None if v is None else v.lstrip(chars) if part[1] == "TrimStart" else v.rstrip(chars) \
                    if part[1] == "TrimEnd" else v.strip(chars)
            else:
                v = None
            if v is None:
                return None
            out += v
        return out

    def resolve(self, name: str, args: list, kwargs: tuple = (), _depth: int = 0):
        """(verbs or None, template or None) the attribute `name` gives with these argument values; None when it is not a
        routing attribute of the project."""
        decls = self.facts.get(name)
        if not decls or len(decls) > 1 or _depth > 5:
            return None
        a, kw = decls[0], dict(kwargs)
        values = {pname: kw[pname] if pname in kw else args[i] if i < len(args) else self.fill(default, {})
                  for i, (pname, default) in enumerate(a.params)}
        if a.parent is not None:
            return self.resolve(a.parent, [self.fill(r, values) for r in a.base_args], (), _depth + 1)
        if a.template is not None:
            return a.verbs, self.fill(a.template, values)
        if a.framework is not None:                  # `: RouteAttribute` / `: HttpDeleteAttribute`, `base("{id:int}")`
            verb = ROUTE_ATTR_BASES[a.framework]
            return ((verb,) if verb else a.verbs), (self.fill(a.base_args[0], values) if a.base_args else "")
        return (a.verbs, None) if a.verbs else None

    def _uses(self, uses: tuple):
        for name, pos, kw in uses:
            r = self.resolve(name, [self.fill(x, {}) for x in pos], tuple((k, self.fill(v, {})) for k, v in kw))
            if r is not None:
                yield r

    def route(self, uses: tuple) -> str | None:
        """The class route the first routing attribute among `uses` gives (`[V3ApiController]` → `api/v3/[controller]`)."""
        return next((tmpl for verbs, tmpl in self._uses(uses) if tmpl is not None and not verbs), None)

    def action(self, uses: tuple) -> tuple[tuple[str, ...], str] | None:
        """(verbs, template) of the first of `uses` that routes an action with a verb (`[RestGetById]`)."""
        return next(((verbs, tmpl) for verbs, tmpl in self._uses(uses) if verbs and tmpl is not None), None)
