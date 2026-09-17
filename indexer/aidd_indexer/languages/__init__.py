"""Language registry (ADR-003).

Adding a language: create `languages/<lang>/` with `queries.scm`, `symbols.py` (a `LanguageSupport`
subclass exported as `LANGUAGES`) and optionally `http.py`, then add the module name to `_MODULES`.
`core/` only ever goes through `by_id` / `by_extension` / `all()` — it never names a language.
"""

from __future__ import annotations

from importlib import import_module

from .base import LanguageSupport

_MODULES = ("go", "typescript", "csharp", "python")

REGISTRY: dict[str, LanguageSupport] = {}
for _m in _MODULES:
    for _lang in import_module(f"{__name__}.{_m}").LANGUAGES:
        REGISTRY[_lang.id] = _lang

_BY_EXT: dict[str, LanguageSupport] = {e: l for l in REGISTRY.values() for e in l.extensions}


def all() -> list[LanguageSupport]:  # noqa: A001 — reads well at the call site: languages.all()
    return list(REGISTRY.values())


def by_id(language_id: str) -> LanguageSupport | None:
    return REGISTRY.get(language_id)


def by_extension(ext: str) -> LanguageSupport | None:
    return _BY_EXT.get(ext.lower())


def parseable() -> set[str]:
    """Language ids with symbol extraction (everything registered)."""
    return set(REGISTRY)


def grammars() -> set[str]:
    return {l.grammar for l in REGISTRY.values()}
