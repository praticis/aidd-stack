"""The mount graph: which router is mounted on which, under what prefix — in one file, then across files.

A router is a `RouterKey` — (id of the function that binds its name, or 0 at module level; the name) — so a
closure's `r` is not the outer `r`. Scanners record an edge per mount (`app.use('/api', router)`,
`r.Mount("/x", sub)`, `include_router(r, prefix=...)`; a group variable gets one with an empty prefix to its
parent) and each route registered on a router.

Across files the graph is composed from per-file summaries, never from the trees of other files. A router
another file can name has a global id (`global_of`, per language): a module-level variable (`var:<unit>:<name>`),
the router a function returns (`ret:<unit>:<function>`), a function's router parameter (`param:<unit>:<function>:<i>`)
or a struct field (`field:<unit>:<path>`); the unit is the file, or the package directory in Go. At the end of a
file (`settle`), a route on such a router waits for the composition; a route whose chain of mounts ends at a router
no other file can name is final. Each file also publishes, per global router, where its own mounts take it — to
another global router or to a top (`""`) — and every mount of a router from elsewhere (`settle`'s `foreign`). A
group of a language that defers it publishes its own prefix too, and `compose` puts it after each chain's.
`compose` follows those edges from each waiting route's router; a router mounted nowhere keeps its routes as they
are, and drops a sub-router's root (`MountedRoot`), which is a route only under a prefix or on the application.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

RouterKey = tuple[int, str]
E = TypeVar("E")
TOP = ""                                   # a router no other file can name: the chain ends there
APP = "@app"                               # the same, when that router is the application: a root mounted on it is `/`


class MountedRoot(str):
    """`"/"` registered on a sub-router: a route only once the router is mounted somewhere."""


@dataclass
class MountGraph:
    edges: list[tuple[RouterKey, RouterKey, str]] = field(default_factory=list)   # (child, parent, prefix)
    routes: list[tuple[int, RouterKey]] = field(default_factory=list)             # (endpoint index, router)

    def mount(self, child: RouterKey, parent: RouterKey, prefix: str) -> None:
        self.edges.append((child, parent, prefix))

    def register(self, index: int, router: RouterKey) -> None:
        self.routes.append((index, router))

    def _up(self) -> dict[RouterKey, list[tuple[RouterKey, str]]]:
        up: dict[RouterKey, list[tuple[RouterKey, str]]] = {}
        for child, parent, p in self.edges:
            up.setdefault(child, []).append((parent, p))
        return up

    def exits(self, key: RouterKey, global_of: Callable[[RouterKey], str | None], is_app: Callable[[RouterKey], bool],
              up: dict | None = None, _seen: frozenset = frozenset()) -> list[tuple[str, str]]:
        """Where the mounts above `key` lead: (the first global router up the chain, or `TOP` / `APP`; the prefix the
        edges on the way add). A router without mounts gives nothing."""
        up = up if up is not None else self._up()
        out: list[tuple[str, str]] = []
        for parent, p in up.get(key, ()):
            if parent in _seen or parent == key:
                continue
            g = global_of(parent)
            if g is not None:
                out.append((g, p))
            elif parent in up:
                out += [(t, pp.rstrip("/") + p) for t, pp in self.exits(parent, global_of, is_app, up, _seen | {key})]
            else:
                out.append((APP if is_app(parent) else TOP, p))
        return list(dict.fromkeys(out))

    def targets(self, key: RouterKey, global_of: Callable[[RouterKey], str | None], is_app: Callable[[RouterKey], bool],
                up: dict | None = None) -> list[tuple[str, str]]:
        """Where a mount on `key` takes another file's router: `key`'s global id, else the mounts above it, else the
        top (`APP` when `key` is the application)."""
        g = global_of(key)
        if g is not None:
            return [(g, "")]
        return self.exits(key, global_of, is_app, up) or [(APP if is_app(key) else TOP, "")]

    def settle(self, endpoints: list[E], rebase: Callable[[E, str], E], is_root: Callable[[E], bool],
               global_of: Callable[[RouterKey], str | None] = lambda _: None,
               foreign: list[tuple[str, RouterKey, str]] = (),
               is_app: Callable[[RouterKey], bool] = lambda _: False) -> tuple[list[tuple[E, str]], list[tuple[str, str, str]]]:
        """Rewrite, in `endpoints`, each route registered here under the prefixes of this file's mounts; drop a
        sub-router's root that no mount reaches. Returns what crosses files: the routes waiting on a global router
        (route, global id) and the edges (child global id, parent global id or `TOP`, prefix) — this file's mounts
        of its global routers, and `foreign`, mounts of another file's router (its id) on a router of this one."""
        up = self._up()
        waiting: list[tuple[E, str]] = []
        drop: list[int] = []
        extra: list[E] = []
        for idx, router in self.routes:
            ep = endpoints[idx]
            g = global_of(router)
            if g is not None:
                waiting.append((ep, g))
                continue
            moved = []
            for target, prefix in self.exits(router, global_of, is_app, up):
                if is_root(ep) and not prefix and target == TOP:
                    continue                                  # a sub-router's root needs a prefix, or the application
                copy = rebase(ep, prefix) if prefix or is_root(ep) and target == APP else ep
                moved.append(copy)
                if target not in (TOP, APP):
                    waiting.append((copy, target))
            if not moved:
                if is_root(ep):
                    drop.append(idx)
                continue
            endpoints[idx] = moved[0]
            extra.extend(moved[1:])
        for idx in sorted(drop, reverse=True):
            del endpoints[idx]
        endpoints.extend(extra)
        edges = [(g, t, p) for child in up if (g := global_of(child)) is not None
                 for t, p in self.exits(child, global_of, is_app, up)]
        for child, parent, prefix in foreign:
            edges += [(child, t, pp.rstrip("/") + prefix) for t, pp in self.targets(parent, global_of, is_app, up)]
        return waiting, list(dict.fromkeys(edges))


def compose(waiting: list[tuple[E, str]], edges: dict[str, list[tuple[str, str]]], rebase: Callable[[E, str], E],
            is_root: Callable[[E], bool], apps: frozenset[str] | set[str] = frozenset(),
            owns: dict[str, list[str]] | None = None) -> dict[int, list[E]]:
    """The plan for the routes waiting on a global router (`id(route)` → what replaces it): one copy per chain of
    edges up to a top or to a router mounted nowhere. A router mounted nowhere keeps its routes; a sub-router's root
    is a route only under a non-empty prefix, or where the chain ends at an application (`apps`: the global routers
    that are one, such as a module's `app = express()`). `owns`: the prefix a global router adds to its own routes,
    after the prefix of the chain that mounts it (`r = r.Group("/v3")`)."""
    chains = _Chains(edges, apps, owns or {})
    plan: dict[int, list[E]] = {}
    for ep, g in waiting:
        if not edges.get(g) and not chains.owns.get(g):
            if is_root(ep) and g not in apps:
                plan[id(ep)] = []
            continue
        prefixes = dict.fromkeys(p for p, app in chains.of(g) if p or app or not is_root(ep))
        plan[id(ep)] = [rebase(ep, p) for p in prefixes]
    return plan


@dataclass
class _Chains:
    """The prefixes of the chains of edges above each global router, as `compose` follows them."""
    edges: dict[str, list[tuple[str, str]]]
    apps: frozenset[str] | set[str]
    owns: dict[str, list[str]]
    memo: dict[str, list[tuple[str, bool]]] = field(default_factory=dict)

    def of(self, g: str, seen: frozenset = frozenset()) -> list[tuple[str, bool]]:
        """(prefix, whether the chain ends at the application)."""
        if g in self.memo:
            return self.memo[g]
        res = list(dict.fromkeys(_with_own(self._mounted(g, seen), self.owns.get(g))))[:16]
        if not seen:
            self.memo[g] = res
        return res

    def _mounted(self, g: str, seen: frozenset) -> list[tuple[str, bool]]:
        outs = self.edges.get(g)
        if not outs:
            return [("", g in self.apps)]                 # mounted nowhere: the router is a top
        res: list[tuple[str, bool]] = []
        for parent, p in outs:
            if parent in (TOP, APP):
                res.append((p, parent == APP))
            elif parent not in seen and len(seen) < 16:
                res += [(pp.rstrip("/") + p, app) for pp, app in self.of(parent, seen | {g})]
        return res


def _with_own(chains: list[tuple[str, bool]], own: list[str] | None) -> list[tuple[str, bool]]:
    """Each chain's prefix followed by each prefix the router adds to its own routes."""
    if not own:
        return chains
    return [(p.rstrip("/") + o, app) for p, app in chains for o in dict.fromkeys(own)]
