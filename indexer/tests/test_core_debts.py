"""The core's debts of architecture: a language's knowledge that the core holds instead of the language's module. Each
case states the right shape and is a strict xfail with the reason: when the code reaches it, the case passes, the xfail
fails the suite, and the mark has to go.

A name belongs to one language when only that language's grammars have it, as a node kind or as a field; a name
several languages share (`identifier`, `arguments`) says nothing about any of them. A framework's or a client
library's vocabulary has no such reference until each language's catalog of frameworks holds it, so its case names
the vocabulary the core holds today."""

import ast
import re
from pathlib import Path

import pytest
from tree_sitter_language_pack import get_language

CORE = Path(__file__).resolve().parents[1] / "aidd_indexer" / "core"
GRAMMARS = {"go": "go", "typescript": "ts", "tsx": "ts", "javascript": "ts", "c_sharp": "csharp", "python": "python"}

# Strings that one language's grammars also have, used where they are for something else.
NOT_SYNTAX = {
    "extract.py": {"call", "import", "receiver", "class"},   # the queries' capture names; a symbol's kind
    "resolve.py": {"class"},                                  # a symbol's kind
    "http_expr.py": {"path"},                                 # a request field's name
    "graph.py": {"result"},                                   # keys of a record
    "manifest.py": {"none", "path"},
    "policy.py": {"source"},
}

FRAMEWORK_NAMES = frozenset({
    "RouterGroup", "Echo", "ServeMux", "APIRouter", "FastAPI", "Flask", "Blueprint", "Starlette", "Sanic", "Quart",
    "resty", "axios", "superagent", "ky", "ofetch", "$fetch", "requests", "httpx", "aiohttp",
    "PostJSON", "GetJSON", "PutJSON", "PatchJSON", "DeleteJSON", "DoJSON", "DoRequest", "NewRequest",
    "NewRequestWithContext", "PostForm", "GetAsync", "GetStringAsync", "GetStreamAsync", "GetByteArrayAsync",
    "GetFromJsonAsync", "PostAsync", "PostAsJsonAsync", "PutAsync", "PutAsJsonAsync", "PatchAsync", "PatchAsJsonAsync",
    "DeleteAsync", "DeleteFromJsonAsync", "SendAsync", "JoinPath", "urljoin", "UrlCombine", "HttpMethod",
    "aspnet", "aspnet-minimal", "fastendpoints",
})


def case(id, why):
    return pytest.param(None, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


def languages_of_names() -> dict[str, set[str]]:
    owners: dict[str, set[str]] = {}
    for grammar, language in GRAMMARS.items():
        lang = get_language(grammar)
        names = {lang.node_kind_for_id(i) for i in range(lang.node_kind_count) if lang.node_kind_is_named(i)}
        names |= {lang.field_name_for_id(i) for i in range(1, lang.field_count + 1)} - {None}
        for name in names:
            owners.setdefault(name, set()).add(language)
    return owners


def one_language_names(path: Path, owners: dict[str, set[str]]) -> set[str]:
    strings = {n.value for n in ast.walk(ast.parse(path.read_text()))
               if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    return {s for s in strings if len(owners.get(s, ())) == 1} - NOT_SYNTAX.get(path.name, set())


@pytest.mark.parametrize("_", [
    case("the-core-names-no-syntax-of-one-language",
         "the core holds node kinds and fields of each language, which belong to each language's module"),
])
def test_the_core_names_no_node_kind_or_field_of_a_single_language(_):
    owners = languages_of_names()
    found = {p.name: sorted(names) for p in sorted(CORE.glob("*.py")) if (names := one_language_names(p, owners))}
    assert found == {}


def test_a_kind_or_field_of_one_language_is_found_and_a_shared_one_is_not():
    owners = languages_of_names()
    assert owners["func_literal"] == {"go"} and owners["receiver"] == {"go"}
    assert len(owners["identifier"]) > 1 and len(owners["arguments"]) > 1


def test_each_string_kept_out_is_still_in_its_module_and_of_one_language():
    owners = languages_of_names()
    for module, kept in NOT_SYNTAX.items():
        strings = {n.value for n in ast.walk(ast.parse((CORE / module).read_text())) if isinstance(n, ast.Constant)}
        assert kept <= strings and all(len(owners[s]) == 1 for s in kept), module


def code_words(path: Path) -> set[str]:
    """The strings of a module's code, docstrings aside, and the words in them (a pattern's alternatives)."""
    tree = ast.parse(path.read_text())
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and n.body and isinstance(n.body[0], ast.Expr)}
    strings = [n.value for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]
    return set(strings) | {w for s in strings for w in re.findall(r"[$\w]+", s)}


@pytest.mark.parametrize("_", [
    case("the-core-names-no-framework-or-client-library",
         "the core holds router types, client libraries and their methods, which belong to each language's frameworks"),
])
def test_the_core_names_no_framework_or_client_library(_):
    found = {p.name: sorted(names) for p in sorted(CORE.glob("*.py")) if (names := FRAMEWORK_NAMES & code_words(p))}
    assert found == {}


def test_each_framework_name_listed_is_still_in_the_cores_code():
    assert FRAMEWORK_NAMES <= set().union(*(code_words(p) for p in CORE.glob("*.py")))
