"""TS's types: the case table (test_ts_types.py) read by them, and the rules past it: the declaration forms a receiver
is read by, what a module's names are across its imports and exports, and a class's or an interface's members through
its bases. Each answer is the type a call's receiver gets, as the resolver asks for it, or the reason it gets none."""

import contextlib
import io

import pytest
from tree_sitter_language_pack import get_parser

from aidd_indexer import languages
from aidd_indexer.cli import extract_and_resolve
from aidd_indexer.core.model import RepoInfo
from aidd_indexer.core.types import Field, RepoTypes, TypeRef, Unknown
from aidd_indexer.languages.typescript.receivers import receiver_of
from aidd_indexer.languages.typescript.scopes import TsScopes
from aidd_indexer.languages.typescript.type_index import OUTSIDE, Outside, qualified, typed
from test_ts_types import CASES, NAMED, _write
from ts_type_rules import MODELS, RULES

TS = [languages.by_id(i) for i in ("typescript", "tsx", "javascript")]


def _scopes(call, src: bytes, cache: dict = {}) -> TsScopes:  # noqa: B006  one per file's source, while it is read
    if cache.get("src") is not src:
        root = call
        while root.parent is not None:
            root = root.parent
        cache.update(src=src, scopes=TsScopes(root, src))
    return cache["scopes"]


# -- the case table, with the receiver read by the types, as the change of behavior will read it --------------------
@pytest.fixture
def read_by_the_types(monkeypatch):
    for lang in TS:
        monkeypatch.setattr(lang, "call_receiver", lambda call, receiver, src, index=None, js=lang.id == "javascript":
                            receiver_of(receiver, _scopes(call, src), js))


def cases(answer: str) -> list:
    return [pytest.param(name, id=name) for name, c in CASES.items() if c.answer == answer]


def answered(root, name: str) -> tuple[set[tuple[str, str]], set[str]]:
    """The case's edges, and the reasons its calls of its method get no type: the receiver's, the type index's for its
    type, or for the method on it."""
    _write(root, name)
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)),
                                      convs=[])
    case = CASES[name]
    use = next(f for f in res.files if f.path.startswith("app/use."))
    sym = {s.id: s for s in res.symbols}
    edges = {(sym[e.callee_id].qualified_name, e.strategy) for e in rv.calls
             if use.id in (e.caller_id, getattr(sym.get(e.caller_id), "file_id", None))
             and (e.method or sym[e.callee_id].name) == case.method}
    calls = [c for c in res.calls if c.file_id == use.id and c.callee_name == case.method and c.receiver is not None]
    types = res.types.of("typescript")
    return edges, {r for r in (reason(types, c, use.path) for c in calls) if r}


def reason(types, call, file: str) -> str | None:
    if call.receiver_type is None:
        return call.receiver_unknown
    found = typed(types, file, call.receiver_type, call.receiver_path)
    if isinstance(found, Outside):
        return OUTSIDE.reason
    found = types.method(found, call.callee_name) if isinstance(found, TypeRef) else found
    return None if isinstance(found, TypeRef) else found.reason


@pytest.mark.parametrize("name", cases("typed"))
def test_a_declared_receiver_reaches_the_declaration_the_checker_names(tmp_path, read_by_the_types, name):
    assert answered(tmp_path, name) == ({(CASES[name].declared[0], "receiver-type")}, set())


@pytest.mark.parametrize("name", cases("unknown"))
def test_an_undecided_receiver_reaches_no_method_by_type_and_says_why(tmp_path, read_by_the_types, name):
    edges, reasons = answered(tmp_path, name)
    by_type = {t for t, s in edges if s.removesuffix("-ambiguous") not in NAMED}
    assert (by_type, reasons) == (set(), {CASES[name].reason})


@pytest.mark.parametrize("name", cases("external"))
def test_a_value_of_a_package_type_reaches_no_homonym_of_the_repo(tmp_path, read_by_the_types, name):
    assert answered(tmp_path, name) == (set(), {CASES[name].reason})


# -- the rules past the table (ts_type_rules.py) ------------------------------------------------------------------
def _extract(root, files: dict[str, str]):
    for rel, body in {"package.json": '{"name": "app"}\n', **files}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)),
                                   convs=[])[0]


def type_of(root, files: dict[str, str], call: str, at: str = "app/use.ts") -> str:
    """The type of the receiver of the call written `call` in the file `at`: its qualified name, `outside:` and the
    package's name, or the reason it has none."""
    res = _extract(root, {"app/models.ts": MODELS, **files})
    src = files[at].encode()
    lang = languages.by_extension("." + at.rsplit(".", 1)[1])
    tree = get_parser(lang.grammar).parse(src)
    stack, node = [tree.root_node], None
    while stack and node is None:
        n = stack.pop()
        node = n if n.type == "call_expression" and n.text.decode() == call else None
        stack.extend(n.children)
    receiver = node.child_by_field_name("function").child_by_field_name("object")
    found = receiver_of(receiver, TsScopes(tree.root_node, src), lang.id == "javascript")
    if isinstance(found, Unknown):
        return found.reason
    found = typed(res.types.of(lang.id), at, *found)
    return qualified(found) if isinstance(found, TypeRef) else f"outside:{found.name}" \
        if isinstance(found, Outside) else found.reason




@pytest.mark.parametrize("files, call, expected, at", [
    pytest.param(*(rule if len(rule) == 4 else (*rule, "app/use.ts")), id=name) for name, rule in RULES.items()])
def test_a_receiver_is_read_by_the_declarations_the_index_reads_across_files(tmp_path, files, call, expected, at):
    assert type_of(tmp_path, files, call, at) == expected


def test_ts_three_languages_share_one_index(tmp_path):
    res = _extract(tmp_path, {"app/models.ts": MODELS})
    types = RepoTypes(res.types._ctx)
    assert types.of("typescript") is types.of("tsx") is types.of("javascript")


def test_a_class_is_an_implementer_of_its_interfaces_and_a_subtype_of_its_bases(tmp_path):
    res = _extract(tmp_path, {"app/models.ts": "export interface I { run(): void }\nexport class Base {}\n"
                                               "export class B extends Base implements I { run() {} }\n"})
    types = res.types.of("typescript")
    b, i, base = (TypeRef("app/models", n) for n in ("B", "I", "Base"))
    assert (types.implementers(i), types.supertypes(b), types.method(b, "run")) == ([b], [base, i], b)


def test_a_supertype_is_listed_once_however_it_is_reached(tmp_path):
    res = _extract(tmp_path, {"app/models.ts": "export interface I {}\nexport class A implements I {}\n"
                                               "export class C extends A implements I {}\n"
                                               "export class X extends Y {}\nexport class Y extends X {}\n"})
    types = res.types.of("typescript")
    a, c, i, x, y = (TypeRef("app/models", n) for n in "ACIXY")
    assert (types.supertypes(c), types.supertypes(x)) == ([a, i], [y])


def test_the_type_services_questions_are_answered_across_files(tmp_path):
    res = _extract(tmp_path, {"app/models.ts": MODELS + "export function make(): B { return new B(); }\n"
                                                        "export interface Maker { made(): A }\n"
                                                        "export class Held { b = new B(); }\n"
                                                        "export class Sub extends Held {}\n",
                              "app/use.ts": 'import { make } from "./models";\nexport const f = () => make();\n'})
    types = res.types.of("typescript")
    a, b, maker, held, sub = (TypeRef("app/models", n) for n in ("A", "B", "Maker", "Held", "Sub"))
    assert (types.return_type("make", "app/use.ts"), types.method_return_type(maker, "made"),
            types.field(held, "b"), types.field(sub, "b")) == (b, a, Field(b, "B", False), Field(b, "B", True))


def test_a_class_with_a_base_a_package_declares_may_get_a_member_from_it(tmp_path):
    res = _extract(tmp_path, {"app/models.ts": 'import { Component } from "react";\n'
                                               "export class V extends Component { go() {} }\n"})
    types = res.types.of("typescript")
    assert types.outside_base(TypeRef("app/models", "V")) and types.method(TypeRef("app/models", "V"), "render") \
        == Unknown("a member a base outside the repo may give")
