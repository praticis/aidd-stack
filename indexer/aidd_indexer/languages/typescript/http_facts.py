"""What a TS/JS file publishes for the others (`HttpResult.publish`), and what it leaves waiting on them (`Pending`)."""

from __future__ import annotations

from typing import NamedTuple

from ...core.model import HttpEndpointInfo


class NestPrefix(NamedTuple):
    """`app.setGlobalPrefix('api', { exclude })` in a module: the prefix, the paths it leaves out, and the exported
    array of paths it names (`<file>:<name>`), if any."""
    prefix: str
    excludes: tuple[str, ...]
    excludes_ref: str | None


class StringArray(NamedTuple):
    """An exported array of strings, by `<file>:<name>`."""
    items: tuple[str, ...]


class NestRoute(NamedTuple):
    """A Nest route, waiting for the global prefix of its module."""
    module: str


class RouteWrapper(NamedTuple):
    """A function that registers routes on the router it is given: the position of the router, the verb (`("verb",
    verb)`) or the position of the argument naming it (`("arg", i)`), the position of the path, the path around it."""
    router_arg: int
    verb: tuple
    path_arg: int
    template: str


class RouteWrapperCall(NamedTuple):
    """A call that may be to a route wrapper: its arguments as (path, verb), where each router argument leads
    (position → (its group prefix, the mount targets)), and the endpoint recorded at the call."""
    args: tuple
    where: dict
    base: HttpEndpointInfo


class WrappedRoute(NamedTuple):
    """A registration inside a route wrapper's body: a template of the wrapper's routes once a call uses it."""
    wrapper: str


class MountWrapper(NamedTuple):
    """A method that mounts what it is given under the path it is given: the position of the path, of the router, and
    whether the method calls the router."""
    path_arg: int
    router_arg: int
    calls_router: bool


class MountWrapperCall(NamedTuple):
    """A call that may be to a mount wrapper: the positions it was read with, the router it hands as a value and as a
    call, and where its receiver leads."""
    path_arg: int
    router_arg: int
    value: str | None
    called: str | None
    target: str
    prefix: str


class Autoload(NamedTuple):
    """A directory `@fastify/autoload` registers: where its plugins are mounted, the prefix, whether folders add theirs."""
    target: str
    prefix: str
    folders: bool
