"""The repo's type service: a language that answers no question leaves every answer `Unknown`; each language's index
is built once, on its first question; and the HTTP pass and the resolver ask the same instance."""

import contextlib
import io

from aidd_indexer import languages
from aidd_indexer.core import integrations
from aidd_indexer.core.types import UNANSWERED, RepoTypes, TypeIndex, TypeRef, Unknown

T = TypeRef("internal.app", "Server")


def test_an_index_that_answers_nothing_says_so():
    idx = TypeIndex()
    answers = [idx.type_named("Server", "main.go"), idx.field(T, "api"), idx.method(T, "Run"), idx.bases(T),
               idx.implementers(T), idx.return_type("app.New", "main.go")]
    assert answers == [UNANSWERED] * 6 and isinstance(UNANSWERED, Unknown)


def test_each_language_builds_its_index_once(monkeypatch):
    built = []

    class Answers(TypeIndex):
        def bases(self, of):
            return [TypeRef("internal.app", "Base")]

    go = languages.by_id("go")
    monkeypatch.setattr(go, "type_index", lambda ctx: built.append(ctx) or Answers())
    types = RepoTypes.of_files("/repo", [], [], {})
    assert types.of("go").bases(T) == [TypeRef("internal.app", "Base")]
    assert types.of("go") is types.of("go") and len(built) == 1
    assert types.of("typescript").bases(T) == UNANSWERED      # a language that answers none
    assert types.of("cobol").bases(T) == UNANSWERED           # nor one the indexer does not know


def test_the_http_pass_and_the_resolver_ask_the_same_instance(tmp_path, monkeypatch):
    from aidd_indexer.cli import extract_tree
    from aidd_indexer.core.model import RepoInfo
    from aidd_indexer.core.resolve import Resolver
    seen = []

    class View(integrations.RepoView):
        def __init__(self, *args):
            super().__init__(*args)
            seen.append(self.types)

    monkeypatch.setattr(integrations, "RepoView", View)
    (tmp_path / "go.mod").write_text("module example.com/x\n\ngo 1.22\n")
    (tmp_path / "main.go").write_text("package main\n\nfunc main() {}\n")
    repo = RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(tmp_path))
    with contextlib.redirect_stderr(io.StringIO()):
        res, extractors = extract_tree(repo)
        resolver = Resolver(res, extractors)
    assert isinstance(res.types, RepoTypes) and seen == [res.types] and resolver.ctx.types is res.types
