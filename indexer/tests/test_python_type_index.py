"""Python's types: the case table (test_python_types.py) read by them, and the rules past it: the declaration forms a
binding is read by, the namespaces a name is looked up in across files, and the MRO. Each answer is the type a call's
receiver gets, as the resolver asks for it, or the reason it gets none."""

import contextlib
import io
import json

import pytest
from tree_sitter_language_pack import get_parser

from aidd_indexer import languages
from aidd_indexer.cli import extract_and_resolve
from aidd_indexer.core.model import RepoInfo
from aidd_indexer.core.types import TypeRef, Unknown
from aidd_indexer.languages.python.receivers import receiver_of
from aidd_indexer.languages.python.scopes import PyScopes
from aidd_indexer.languages.python.type_index import OUTSIDE, Outside, qualified, ref, typed
from test_python_types import CASES, edges_of, extracted, typed_targets

PYTHON = languages.by_id("python")


# -- the case table: each case's edges, and the reason a receiver gets no type ----------------------------------------
def cases(answer: str) -> list:
    return [pytest.param(c, id=i) for i, c in CASES.items() if c.answer == answer]


def answered(root, case) -> tuple[set[tuple[str, str]], set[str]]:
    """The case's edges, and the reasons its calls of its method get no type: the file's for the receiver, the type
    index's for its type, or for the method on it."""
    res, rv = extracted(root, case)
    use = next(f.id for f in res.files if f.path == "app/use.py")
    calls = [c for c in res.calls if c.file_id == use and c.callee_name == case.method and c.receiver is not None]
    return edges_of(res, rv, case), {r for r in (reason(res.types.of("python"), c, case.method) for c in calls) if r}


def reason(types, call, method: str) -> str | None:
    if call.receiver_type is None:
        return call.receiver_unknown
    found = typed(types, "app/use.py", call.receiver_type, call.receiver_path)
    if isinstance(found, Outside):
        return OUTSIDE.reason
    found = types.method(found, method) if isinstance(found, TypeRef) else found
    return None if isinstance(found, TypeRef) else found.reason


@pytest.mark.parametrize("case", cases("typed"))
def test_a_declared_receiver_reaches_the_method_cpython_runs(tmp_path, case):
    assert answered(tmp_path, case) == ({(case.runs, "receiver-type")}, set())


@pytest.mark.parametrize("case", cases("unknown"))
def test_an_undecided_receiver_reaches_no_method_by_type_and_says_why(tmp_path, case):
    edges, reasons = answered(tmp_path, case)
    assert (typed_targets(edges), reasons) == (set(), {case.reason})


@pytest.mark.parametrize("case", cases("external"))
def test_a_value_of_an_external_class_reaches_no_homonym_of_the_repo(tmp_path, case):
    assert answered(tmp_path, case) == (set(), {case.reason})


# -- the rules past the table --------------------------------------------------------------------------------------


def _extract(root, files: dict[str, str]):
    for rel, body in {"pyproject.toml": '[project]\nname = "app"\n', **files}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    repo = RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root))
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(repo)[0]


def type_of(root, files: dict[str, str], call: str, at: str = "app/use.py") -> str:
    """The type of the receiver of the call written `call` in the file `at`: its qualified name, `outside:` and the
    package's name, or the reason it has none."""
    res = _extract(root, files)
    src = files[at].encode()
    tree = get_parser("python").parse(src)
    stack, node = [tree.root_node], None
    while stack and node is None:
        n = stack.pop()
        node = n if n.type == "call" and n.text.decode() == call else None
        stack.extend(n.children)
    found = receiver_of(node.child_by_field_name("function").child_by_field_name("object"), PyScopes(tree.root_node, src))
    if isinstance(found, Unknown):
        return found.reason
    found = typed(res.types.of("python"), at, *found)
    return qualified(found) if isinstance(found, TypeRef) else f"outside:{found.name}" \
        if isinstance(found, Outside) else found.reason


MODELS = "class A:\n    def run(self): pass\nclass B(A):\n    def run(self): pass\n"
RULES = {
    "a-generic-of-the-repo-is-its-origin": (
        {"app/models.py": "from typing import Generic, TypeVar\nT = TypeVar('T')\nclass Repo(Generic[T]):\n"
                          "    def find(self): pass\n",
         "app/use.py": "from app.models import Repo\ndef f(r: Repo[int]): return r.find()\n"}, "r.find()",
        "app/models:Repo"),
    "typing-through-its-module": (
        {"app/models.py": MODELS,
         "app/use.py": "import typing\nfrom app import models\ndef f(x: typing.Optional[models.B]): return x.run()\n"},
        "x.run()", "app/models:B"),
    "a-union-with-none": (
        {"app/models.py": MODELS,
         "app/use.py": "from typing import Union\nfrom app.models import B\ndef f(x: Union[B, None]): return x.run()\n"},
        "x.run()", "app/models:B"),
    "an-optional-named-by-a-class-of-the-repo-is-that-class": (
        {"app/models.py": MODELS + "class Optional:\n    def run(self): pass\n",
         "app/use.py": "from app.models import Optional, B\ndef f(x: Optional[B]): return x.run()\n"},
        "x.run()", "app/models:Optional"),
    "a-nested-class": (
        {"app/use.py": "class Outer:\n    class Inner:\n        def run(self): pass\n        def go(self): return self.run()\n"},
        "self.run()", "app/use:Outer.Inner"),
    "a-class-defined-in-a-function": (
        {"app/use.py": "def f():\n    class C:\n        def run(self): pass\n        def go(self): return self.run()\n"},
        "self.run()", "a class defined in a function"),
    "a-static-methods-first-parameter": (
        {"app/use.py": "class C:\n    @staticmethod\n    def go(x): return x.run()\n"},
        "x.run()", "a parameter with no annotation"),
    "super-in-a-class-of-two-bases": (
        {"app/models.py": MODELS,
         "app/use.py": "from app.models import A, B\nclass C(B, A):\n    def go(self): return super().run()\n"},
        "super().run()", "super() in a class of several bases, or of none"),
    "a-namespace-package": (
        {"app/ns/mod.py": "class C:\n    def run(self): pass\n",
         "app/use.py": "from app.ns import mod\ndef f(): return mod.C().run()\n"}, "mod.C().run()", "app/ns/mod:C"),
    "a-submodule-through-its-package": (
        {"app/__init__.py": "", "app/sub/__init__.py": "", "app/sub/m.py": "class C:\n    def run(self): pass\n",
         "app/use.py": "import app.sub.m\ndef f(): return app.sub.m.C().run()\n"}, "app.sub.m.C().run()", "app/sub/m:C"),
    "an-import-cycle": (
        {"app/__init__.py": "", "app/a.py": "from app.b import x\n", "app/b.py": "from app.a import x\n",
         "app/use.py": "from app.a import x\ndef f(): return x.run()\n"},
        "x.run()", "a chain of names longer than the index follows"),
    "two-definitions": (
        {"app/use.py": "class C:\n    def run(self): pass\nclass C:\n    def run(self): pass\n"
                       "def f(): return C().run()\n"}, "C().run()", "bindings that disagree"),
    "an-attribute-two-methods-set-apart": (
        {"app/models.py": MODELS,
         "app/use.py": "from app.models import A, B\nclass C:\n    def __init__(self): self.x = A()\n"
                       "    def reset(self): self.x = B()\n    def go(self): return self.x.run()\n"},
        "self.x.run()", "bindings that disagree"),
    "an-annotation-in-the-class-decides-the-attribute": (
        {"app/models.py": MODELS,
         "app/use.py": "from app.models import A, B\nclass C:\n    x: A\n    def __init__(self): self.x = A()\n"
                       "    def reset(self): self.x = B()\n    def go(self): return self.x.run()\n"},
        "self.x.run()", "app/models:A"),
    "an-instance-bound-again-assigns-no-attribute": (
        {"app/models.py": MODELS,
         "app/use.py": "from app.models import B\nclass C:\n    def __init__(self):\n        self = object()\n"
                       "        self.x = B()\n    def go(self): return self.x.run()\n"},
        "self.x.run()", "its module or class declares no such name"),
    "a-name-a-function-imports": (
        {"app/models.py": MODELS, "app/use.py": "def f():\n    from app import models\n    return models.run()\n"},
        "models.run()", "a name a function imports"),
    "a-function-imports-a-class-and-calls-it": (
        {"app/models.py": MODELS, "app/use.py": "def f():\n    from app.models import B\n    return B().run()\n"},
        "B().run()", "a name bound inside a function, read as a type"),
    "a-method-result": (
        {"app/models.py": MODELS,
         "app/use.py": "from app.models import B\nclass C:\n    def make(self) -> B: return B()\n"
                       "    def go(self):\n        x = self.make()\n        return x.run()\n"},
        "x.run()", "the result of a method call"),
    "a-module-variable-of-another-module": (
        {"app/models.py": MODELS + "default = B()\n",
         "app/use.py": "from app.models import default\ndef f(): return default.run()\n"},
        "default.run()", "app/models:B"),
    "an-attribute-of-a-package-value": (
        {"app/use.py": "from fastapi import Request\ndef f(request: Request): return request.user.save()\n"},
        "request.user.save()", "an attribute of a type outside the repo"),
    "a-method-whose-result-names-it": (
        {"app/use.py": "class C:\n    def list(self) -> list[str]: pass\n    def go(self): return self.list()\n"},
        "self.list()", "app/use:C"),
    "a-package-module": (
        {"app/use.py": "import requests\ndef f(): return requests.Session().get()\n"},
        "requests.Session().get()", "outside:requests.Session"),
    "a-module-the-repo-holds-under-no-root-of-its-imports": (
        {"lib/shop/models.py": MODELS, "app/use.py": "from shop.models import B\ndef f(): return B().run()\n"},
        "B().run()", "a module of the repo's names, under a root its imports are not looked for in"),
    "a-name-a-module-may-get-by-a-star-import": (
        {"app/models.py": MODELS, "app/everything.py": "from app.models import *\n",
         "app/use.py": "from app import everything\ndef f(): return everything.B().run()\n"},
        "everything.B().run()", "a name only a star import may bind"),
    "a-class-a-module-of-a-star-import-declares": (
        {"app/models.py": MODELS, "app/everything.py": "from app.models import *\nclass C:\n    def run(self): pass\n",
         "app/use.py": "from app import everything\ndef f(): return everything.C().run()\n"},
        "everything.C().run()", "app/everything:C"),
}


@pytest.mark.parametrize("files,call,expected", [pytest.param(*v, id=k) for k, v in RULES.items()])
def test_a_receiver_gets_the_type_its_declarations_give_or_says_why_not(tmp_path, files, call, expected):
    assert type_of(tmp_path, files, call) == expected


def _types(tmp_path, files: dict[str, str]):
    return _extract(tmp_path, files).types.of("python")


def test_the_mro_is_c3s_and_stops_at_the_first_base_outside_the_repo(tmp_path):
    types = _types(tmp_path, {"app/use.py": "from threading import Thread\nclass A: pass\nclass B(A): pass\n"
                                            "class C(A): pass\nclass D(B, C): pass\nclass E(B, Thread, C): pass\n"
                                            "class F(object): pass\n"})
    names = {n: ref(f"app/use:{n}") for n in "ADEF"}
    assert [t.name for t in types.supertypes(names["D"])] == ["B", "C", "A"]
    assert [t.name for t in types.supertypes(names["E"])] == ["B"]
    assert (types.outside_base(names["D"]), types.outside_base(names["E"]), types.outside_base(names["F"])) \
        == (False, True, False)
    assert types.method(names["E"], "start").reason == "a method a base outside the repo may give, ahead in the MRO"


def test_bases_cpython_cannot_order_give_no_supertype(tmp_path):
    types = _types(tmp_path, {"app/use.py": "class A: pass\nclass B(A): pass\nclass C(A, B): pass\n"})
    assert types.supertypes(ref("app/use:C")) == [] and types.method(ref("app/use:C"), "x").reason \
        == "bases CPython cannot order"


def test_a_module_and_a_class_name_their_members_apart():
    assert (PYTHON.member_name("app/service", "run"), PYTHON.member_name("app/models:B", "run")) \
        == ("app/service:run", "app/models:B.run")


def test_the_index_is_built_once_per_file_and_handed_to_the_hooks_that_read_the_file(tmp_path, monkeypatch):
    built, read = [], []
    index, facts = PYTHON.file_index, PYTHON.file_facts
    monkeypatch.setattr(PYTHON, "file_index", lambda root, src: built.append(index(root, src)) or built[-1])
    monkeypatch.setattr(PYTHON, "file_facts", lambda root, src, i=None: read.append(i) or facts(root, src, i))
    monkeypatch.setattr(PYTHON, "call_receiver", lambda call, receiver, src, i=None: read.append(i))
    _extract(tmp_path, {"app/a.py": "def f(x):\n    return x.run()\n", "app/b.py": "y = 1\n"})
    assert [type(i) for i in built] == [PyScopes, PyScopes] and len(read) == 3
    assert {id(i) for i in read} == {id(i) for i in built}


def test_the_facts_are_values():
    src = b"class C:\n    def m(self) -> 'C': self.x = C()\n"
    root = get_parser("python").parse(src).root_node
    facts = json.loads(json.dumps(PYTHON.file_facts(root, src, PYTHON.file_index(root, src))))
    assert facts[0]["C"][1] == {"m": ["function", "C", ""], "x": ["value", "call:C", ""]}
