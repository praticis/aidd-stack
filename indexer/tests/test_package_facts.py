"""A language's package facts join two files' values under the rule each field declares: the same facts whether the
files add to the directory in turn, or each file's part is joined afterwards in file order."""

from dataclasses import dataclass, fields
from typing import ClassVar

import pytest

from aidd_indexer.core.http_base import PackageContext
from aidd_indexer.core.http_view import RepoView
from aidd_indexer.core.package_facts import AGREE, LAST, UNION, PackageFacts, joined_by
from aidd_indexer.languages.go.package_facts import GoFacts
from aidd_indexer.languages.python.package_facts import PyFacts
from aidd_indexer.languages.typescript.package_facts import TsFacts

LANGUAGE_FACTS = [GoFacts, PyFacts, TsFacts]


@dataclass
class _Facts(PackageFacts):
    key: ClassVar[str] = "test"
    one: dict = joined_by(AGREE)
    last: dict = joined_by(LAST)
    seen: set = joined_by(UNION)


FILES = [                                       # what three files of a directory add, in file order
    [("one", "a", 1), ("one", "b", 2), ("last", "x", "first"), ("seen", "p", None)],
    [("one", "a", 1), ("one", "b", 3), ("last", "x", "second"), ("seen", "q", None)],
    [("one", "b", 2), ("one", "c", 4), ("seen", "p", None)],
]


def test_each_rule():
    facts = _Facts()
    for name, key, value in (add for adds in FILES for add in adds):
        facts.put(name, key, value)
    assert facts.one == {"a": 1, "b": None, "c": 4}         # once disputed, a value stays unknown
    assert facts.last == {"x": "second"}
    assert facts.seen == {"p", "q"}


def test_joining_each_files_part_equals_adding_in_turn():
    in_turn, joined = _Facts(), _Facts()
    for adds in FILES:
        part = _Facts()
        for name, key, value in adds:
            in_turn.put(name, key, value)
            part.put(name, key, value)
        joined.join(part)
    assert joined == in_turn


def test_reading_leaves_the_context_as_it_was():
    ctx = PackageContext()
    assert GoFacts.read(ctx).passthrough == {}
    assert ctx.facts == {}
    GoFacts.of(ctx).put("passthrough", "BaseUri", 0)
    assert GoFacts.read(ctx).passthrough == {"BaseUri": 0}


@pytest.mark.parametrize("kind", LANGUAGE_FACTS)
def test_every_field_of_a_language_says_how_it_joins(kind):
    assert all(f.metadata.get("join") in (AGREE, LAST, UNION) for f in fields(kind))


def test_each_language_has_a_key_of_its_own():
    assert len({kind.key for kind in LANGUAGE_FACTS}) == len(LANGUAGE_FACTS)


def test_the_directory_context_holds_no_language_fact():
    own = {f.name for kind in LANGUAGE_FACTS for f in fields(kind)}
    assert set(vars(PackageContext())) & own == set()


def test_a_lookup_across_the_repo_is_a_question_to_the_view():
    a, b, c = PackageContext(), PackageContext(), PackageContext()
    PyFacts.of(a).put("classes", "BaseRouter", (("APIRouter",), None))
    PyFacts.of(c).put("classes", "BaseRouter", (("Router",), None))
    view = RepoView(None, [], None, {"a": a, "b": b, "c": c})
    assert view.defining(PyFacts, "classes", "BaseRouter") == [a, c]
    assert view.defining(PyFacts, "classes", "Other") == []
    assert view.defining(GoFacts, "passthrough", "BaseRouter") == []
