"""The one rule for whether a call and a route meet, shared by the linker, the MCP and the corpus scorer: paths compare
by `path_key` (placeholder names do not matter), without case for a framework that routes so, and a method meets its
equal or `ANY` on either side."""

from __future__ import annotations

from .paths import normalize_path, path_key

# Frameworks that match a request path without case (`/api/TodoItems` is `/api/todoitems`): ASP.NET routing.
CASE_INSENSITIVE = frozenset({"aspnet", "aspnet-minimal", "fastendpoints"})


def methods_compatible(a: str, b: str) -> bool:
    return a == b or a == "ANY" or b == "ANY"


def compared(key: str, framework: str | None) -> str:
    """A path key as the route's framework compares it."""
    return key.lower() if framework in CASE_INSENSITIVE else key


def is_segment_suffix(short: str, long: str) -> bool:
    """`/v1/x/{param}` is a suffix of `/api/v1/x/{param}` — path keys start with `/`, so the
    boundary is a whole segment by construction."""
    return len(long) > len(short) and long.endswith(short)


def query_key(path: str) -> str:
    """The key of a path someone asks about, written as a route or a call would be (`/users/:id/`, `api/users/{userId}`,
    `https://host/v1/x?y=1`)."""
    return path_key(normalize_path(path))
