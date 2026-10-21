"""Language registry.

Adding a language: create `languages/<lang>/` with `queries.scm`, `symbols.py` (a `LanguageSupport`
subclass exported as `LANGUAGES`) and optionally `http.py`, then add the module name to `_MODULES`.
`core/` only ever goes through `by_id` / `by_extension` / `all()` — it never names a language.
"""

from __future__ import annotations

from importlib import import_module

from .base import LanguageSupport

_MODULES = ("go", "typescript", "csharp", "python")

_REGISTRY: dict[str, LanguageSupport] = {}
_BY_EXT: dict[str, LanguageSupport] = {}


def _registry() -> dict[str, LanguageSupport]:
    """The languages, loaded on first use: their modules import `core/`, so loading them while `core/` is being
    imported would be a cycle."""
    if not _REGISTRY:
        for m in _MODULES:
            for lang in import_module(f"{__name__}.{m}").LANGUAGES:
                _REGISTRY[lang.id] = lang
        _BY_EXT.update({e: lang for lang in _REGISTRY.values() for e in lang.extensions})
    return _REGISTRY


def all() -> list[LanguageSupport]:  # noqa: A001 — reads well at the call site: languages.all()
    return list(_registry().values())


def by_id(language_id: str) -> LanguageSupport | None:
    return _registry().get(language_id)


def by_extension(ext: str) -> LanguageSupport | None:
    _registry()
    return _BY_EXT.get(ext.lower())


def parseable() -> set[str]:
    """Language ids with symbol extraction (everything registered)."""
    return set(_registry())


def grammars() -> set[str]:
    return {lang.grammar for lang in _registry().values()}
