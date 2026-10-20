"""What a C# file publishes for the others (`HttpResult.publish`), and what it leaves waiting on them (`Pending`). A
recipe is a route template over a routing attribute's constructor parameters, filled by `_RouteAttributes.fill`."""

from __future__ import annotations

from typing import NamedTuple

from ...core.model import HttpEndpointInfo


# -- facts, by the name of the class (or of what) they describe ----------------------------------------------------
class CsClass(NamedTuple):
    """A class, for the controllers that derive from it in other files: its own `[Route]`s, whether it is `partial`,
    the attributes that may be routing attributes of the project, and its bases' simple names."""
    routes: tuple[str, ...]
    partial: bool
    uses: tuple
    bases: tuple[str, ...]


class Action(NamedTuple):
    """An action a derived controller takes, under its own route: the endpoint as written, the template, whether it is
    absolute, the method's name and arity."""
    proto: HttpEndpointInfo
    template: str
    absolute: bool
    name: str
    arity: int


class AttrAction(NamedTuple):
    """An action that only a routing attribute of the project may route (`[RestGetById]`): the endpoint at the
    attribute, the attributes as uses, a `[Route]` beside them ("" for a plain action, None for none), the method's
    name and arity."""
    proto: HttpEndpointInfo
    uses: tuple
    extra: str | None
    name: str
    arity: int


class NonAction(NamedTuple):
    """`[NonAction] override`: a base's action that is not one in this class nor below it."""
    name: str
    arity: int


class Area(NamedTuple):
    """`[Area("Admin")]`, which derived controllers inherit."""
    name: str


class RouteAttr(NamedTuple):
    """A routing attribute of the project: the framework attribute it derives from, or another of the project's, its
    constructor's parameters (name, default recipe), what it hands its base, its `Template` and its `HttpMethods`."""
    framework: str | None
    parent: str | None
    params: tuple
    base_args: tuple
    template: tuple | None
    verbs: tuple[str, ...] | None


class DefaultApiVersion(NamedTuple):
    """Asp.Versioning's `DefaultApiVersion`, the version of a controller that declares none."""
    version: str


class CharArray(NamedTuple):
    """`static readonly char[] X = { '~', '/' }`, by `Class.Field`: what a `TrimStart(X)` trims."""
    chars: str


class RouteConvention(NamedTuple):
    """A model convention class that rewrites the attribute routes."""


class ConventionUse(NamedTuple):
    """`options.Conventions.Add(new T(a, b))`, by the convention's class: its arguments as recipes."""
    args: tuple


class FastBase(NamedTuple):
    """A class over FastEndpoints' own endpoint (`AppEndpoint<..>`): its bases' simple names."""
    bases: tuple[str, ...]


class FeGroup(NamedTuple):
    """A FastEndpoints group: its prefix as a recipe (None: one its file cannot read) and its parent group's name."""
    prefix: tuple | None
    parent: str | None


class FePrefix(NamedTuple):
    """FastEndpoints' global `RoutePrefix`, as a recipe (None: one its file cannot read)."""
    prefix: tuple | None


class ClientWrapper(NamedTuple):
    """A method that is a client wrapper, by `Class.Method`: the parameter its path is built around, the text before
    and after it, and the verb."""
    index: int
    before: str
    after: str
    verb: str


# -- what a route or a call waits for ------------------------------------------------------------------------------
class InheritedRoute(NamedTuple):
    """A route of a controller with no `[Route]` of its own, waiting for its bases': the bases, the controller's and
    the action's names, whether it is the root, the area, the attribute uses, the versions, and the OData template
    (None: not OData; "": OData would not route it)."""
    bases: tuple[str, ...]
    controller: str
    action: str
    root: bool
    area: str
    uses: tuple
    versions: tuple[str, ...]
    odata_template: str | None


class AttrActionRoute(NamedTuple):
    """An action only a routing attribute of the project may route, waiting for the attributes and the controller's
    route: the action, the controller, its `[Route]`s, its attribute uses, its bases, its area and versions."""
    action: AttrAction
    controller: str
    routes: tuple[str, ...]
    uses: tuple
    bases: tuple[str, ...]
    area: str
    versions: tuple[str, ...]


class InheritedActions(NamedTuple):
    """A controller waiting for the actions its bases declare: its bases, its name, its `[Route]`s, its area, the
    actions it declares itself (name, arity), its attribute uses and versions."""
    bases: tuple[str, ...]
    controller: str
    routes: tuple[str, ...]
    area: str
    own: frozenset
    uses: tuple
    versions: tuple[str, ...]


class AreaRoute(NamedTuple):
    """A route with an `[area]` token, waiting for the `[Area]` of a base among `bases`."""
    bases: tuple[str, ...]


class DefaultVersionRoute(NamedTuple):
    """A route with version placeholders and no version declared, waiting for the repo's default version."""
    names: tuple[str, ...]


class FastEndpointRoutes(NamedTuple):
    """An endpoint class's routes, waiting for a base of the project to reach FastEndpoints' own."""
    bases: tuple[str, ...]
    endpoints: tuple


class FePrefixOverride(NamedTuple):
    """A FastEndpoints route that overrides the global prefix with its own (a recipe)."""
    prefix: tuple | None


class FeGroupRoute(NamedTuple):
    """A FastEndpoints route, waiting for the prefixes of its groups (`Group<T>()`, in order)."""
    groups: tuple[str, ...]


class ClientWrapperCall(NamedTuple):
    """A call on a receiver of a declared type, waiting to learn whether that type's method is a client wrapper."""
    receiver_type: str
    name: str
    args: tuple
