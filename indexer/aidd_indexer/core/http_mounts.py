"""The mount graph of one file: which router is mounted on which, under what prefix.

A router is a `RouterKey` — (id of the function that binds its name, or 0 at module level; the name) — so a
closure's `r` is not the outer `r`. Scanners record an edge per mount (`app.use('/api', router)`,
`r.Mount("/x", sub)`, `include_router(r, prefix=...)`; a group variable gets one with an empty prefix to its
parent) and each route registered on a router. At the end of the file `apply` gives every such route each chain
of mounts above its router; a sub-router's root (`MountedRoot`) that nothing mounts is dropped.

This is the per-file part of the mount graph. Across files the same graph is composed from per-file summaries
(routers exported, mounts by imported name), never from the trees of other files (F1.13).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

RouterKey = tuple[int, str]
E = TypeVar("E")


class MountedRoot(str):
    """`"/"` registered on a sub-router: a route only if this file mounts the router under a prefix."""


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

    def prefixes(self, router: RouterKey, _up: dict | None = None) -> list[str]:
        """Every non-empty prefix the chains of mounts above `router` give, in order, without repeats."""
        up = _up if _up is not None else self._up()

        def chains(key: RouterKey, seen: frozenset) -> list[str]:
            if key in seen or key not in up:
                return [""]
            return [pp.rstrip("/") + p for parent, p in up[key] for pp in chains(parent, seen | {key})]

        return [c for c in dict.fromkeys(chains(router, frozenset())) if c]

    def apply(self, endpoints: list[E], rebase: Callable[[E, str], E], is_root: Callable[[E], bool]) -> None:
        """Rewrite, in `endpoints`, each route registered here: one copy per prefix (`rebase`), or none at all for an
        unmounted sub-router root (`is_root`). Only the indexes registered here are touched."""
        if not self.routes:
            return
        up = self._up()
        drop: list[int] = []
        extra: list[E] = []
        for idx, router in self.routes:
            prefixes = self.prefixes(router, up)
            if not prefixes:
                if is_root(endpoints[idx]):
                    drop.append(idx)
                continue
            moved = [rebase(endpoints[idx], pre) for pre in prefixes]
            endpoints[idx] = moved[0]
            extra.extend(moved[1:])
        for idx in sorted(drop, reverse=True):
            del endpoints[idx]
        endpoints.extend(extra)
