"""What a type is in a declarative convention: the first role whose names, bases or declaration text it matches."""

from __future__ import annotations

import fnmatch
from typing import Any

from ..core.model import SymbolInfo
from .declarations import Declarations

Roles = list[tuple[str, dict[str, Any]]]


def role_of(s: SymbolInfo, roles: Roles, declarations: Declarations) -> str | None:
    ancestors = None
    for role, spec in roles:
        if spec.get("name") and any(fnmatch.fnmatchcase(s.name, g) for g in spec["name"]):
            return role
        if spec.get("extends"):
            ancestors = ancestors if ancestors is not None else declarations.ancestors(s, {s.id})
            if any(n in ancestors for n in spec["extends"]):
                return role
        if spec.get("declares") and any(d in declarations.header(s) for d in spec["declares"]):
            return role
    return None


def assign(types: list[SymbolInfo], roles: Roles,
           declarations: Declarations) -> tuple[dict[str, str], dict[str, set[str]]]:
    """Each type's role by its id, and the roles of the types each file declares."""
    by_type: dict[str, str] = {}
    by_file: dict[str, set[str]] = {}
    for s in types:
        role = role_of(s, roles, declarations)
        if role is not None:
            by_type[s.id] = role
            by_file.setdefault(s.file_id, set()).add(role)
    return by_type, by_file
