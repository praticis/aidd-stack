"""The repo's type service: what type the code declares for a value, asked by the call resolver and by the HTTP
scanners alike, so the two never hold two answers to one question. Each language answers from its files' type facts,
built once per repo; a question it cannot answer gets `Unknown` with the reason, never a guess."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from .. import languages
from ..languages.base import ResolveContext

if TYPE_CHECKING:
    from .model import FileInfo, ModuleInfo


class TypeRef(NamedTuple):
    """A type the repo declares: its package, in the language's own terms ("" for the root), and its name."""
    package: str
    name: str


class Unknown(NamedTuple):
    reason: str


class Field(NamedTuple):
    """A field's type: resolved where its struct or class is declared, the text that declaration writes, and whether
    it was found through an embedded or a base type."""
    type: TypeRef | Unknown
    written: str
    promoted: bool


UNANSWERED = Unknown("the language does not answer this question")


class TypeIndex:
    """One language's answers. Every question gets `Unknown` unless the language answers it."""

    def type_named(self, written: str, file: str) -> TypeRef | Unknown:
        """The type `written` (`pw.Policy`, `*Router`) means in the file at path `file`."""
        return UNANSWERED

    def field(self, owner: TypeRef, name: str) -> Field | Unknown:
        return UNANSWERED

    def method(self, owner: TypeRef, name: str) -> TypeRef | Unknown:
        """The type that declares `owner`'s method `name`: `owner` itself, or a type it embeds or derives from."""
        return UNANSWERED

    def bases(self, of: TypeRef) -> list[TypeRef | Unknown] | Unknown:
        """The types `of` derives from or embeds; one the repo does not declare is `Unknown`."""
        return UNANSWERED

    def implementers(self, interface: TypeRef) -> list[TypeRef] | Unknown:
        return UNANSWERED

    def return_type(self, function: str, file: str, result: int = 0) -> TypeRef | Unknown:
        """The declared type of result number `result` of the function `function` (`pkg.New`), called from the file at
        path `file`."""
        return UNANSWERED

    def method_return_type(self, owner: TypeRef, method: str, result: int = 0) -> TypeRef | Unknown:
        """The declared type of result number `result` of `owner`'s method `method`, declared on `owner` or on a type
        it embeds or derives from."""
        return UNANSWERED


class RepoTypes:
    """Each language's `TypeIndex`, built on its first question from every file's type facts."""

    def __init__(self, ctx: ResolveContext) -> None:
        self._ctx = ctx
        self._by_language: dict[str, TypeIndex] = {}

    @classmethod
    def of_files(cls, root: str, files: list[FileInfo], modules: list[ModuleInfo],
                 facts: dict[str, dict]) -> RepoTypes:
        """From the repo's files, modules and each file's type facts (by file id)."""
        ctx = ResolveContext(Path(root), {f.path: f for f in files}, {m.path: m for m in modules},
                             {m.id: m for m in modules}, {f.id: f for f in files}, {}, facts=facts)
        return cls(ctx)

    def of(self, language: str) -> TypeIndex:
        if language not in self._by_language:
            lang = languages.by_id(language)
            found = lang.type_index(self._ctx) if lang is not None else None
            self._by_language[language] = found if found is not None else TypeIndex()
        return self._by_language[language]
