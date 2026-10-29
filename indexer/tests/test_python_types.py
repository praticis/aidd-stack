"""Python's answers to which binding a name refers to and what type that binding declares, which the resolver asks to
type a call's receiver for `CALLS` (the HTTP scanner's questions are test_python_routers.py's). The two questions are
apart: a scope trap binds a name to a declaration that is not its own, and a declaration form reads the type of the
right one. The method a case names is the one CPython runs for its call: every case that can run here is run, and the
method it enters is compared with the case. What the extraction gives each case, and why a receiver gets no type, is
test_python_type_index.py's."""

import contextlib
import io
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "checks"))
from python_scopes import compare  # noqa: E402

PYPROJECT = '[project]\nname = "app"\n'
MODELS = """class A:
    def run(self): pass


class B:
    def run(self): pass


class Base:
    def run(self): pass


def make() -> B:
    return B()


def build():
    return B()
"""
SERVICE = "def run(): pass\n"
NAMED = ("same-file", "same-module", "unique-name")
INHERITED = ("inherited", "inherited-impl")     # an edge to the type: the method may come from a base outside the repo


class Case(NamedTuple):
    use: str                    # app/use.py; its `main()` makes the call
    runs: str | None            # the method CPython runs for the call; None for a case that cannot run here
    answer: str                 # typed: the declarations decide it; unknown: they do not; external: no repo method
    wrong: str | None = None    # what a binding that is not the name's own, or a misread declaration, would give
    method: str = "run"
    reason: str | None = None   # unknown and external: why the declarations in sight give no type


B_RUN, BASE_RUN = "app/models:B.run", "app/models:Base.run"

# -- a declaration form gives the type of the binding the name refers to ------------------------------------------
DECLARED = {
    "self": Case("class C:\n    def run(self): pass\n    def go(self): return self.run()\n"
                 "def main(): return C().go()\n", "app/use:C.run", "typed"),
    "cls": Case("class C:\n    @classmethod\n    def run(cls): pass\n    @classmethod\n    def go(cls): return cls.run()\n"
                "def main(): return C.go()\n", "app/use:C.run", "typed"),
    "super": Case("from app.models import Base\nclass C(Base):\n    def run(self): pass\n"
                  "    def go(self): return super().run()\ndef main(): return C().go()\n", BASE_RUN, "typed"),
    "a-method-of-a-repo-base": Case("from app.models import Base\nclass C(Base):\n    def go(self): return self.run()\n"
                                    "def main(): return C().go()\n", BASE_RUN, "typed"),
    "a-repo-base-ahead-of-an-external-one": Case(
        "from threading import Thread\nfrom app.models import Base\nclass C(Base, Thread):\n"
        "    def go(self): return self.run()\ndef main(): return C().go()\n", BASE_RUN, "typed"),
    "a-call-of-a-class": Case("from app.models import B\ndef main(): return B().run()\n", B_RUN, "typed"),
    "a-local-of-a-call-of-a-class": Case("from app.models import B\ndef main():\n    x = B()\n    return x.run()\n",
                                         B_RUN, "typed"),
    "an-aliased-import": Case("from app.models import B as Bee\ndef main():\n    x = Bee()\n    return x.run()\n",
                              B_RUN, "typed"),
    "a-class-of-an-imported-module": Case("from app import models\ndef main():\n    x = models.B()\n"
                                          "    return x.run()\n", B_RUN, "typed"),
    "a-parameter": Case("from app.models import B\ndef f(x: B): return x.run()\ndef main(): return f(B())\n",
                        B_RUN, "typed"),
    "optional": Case("from typing import Optional\nfrom app.models import B\ndef f(x: Optional[B]): return x.run()\n"
                     "def main(): return f(B())\n", B_RUN, "typed"),
    "or-none": Case("from app.models import B\ndef f(x: B | None): return x.run()\ndef main(): return f(B())\n",
                    B_RUN, "typed"),
    "a-string": Case('from app.models import B\ndef f(x: "B"): return x.run()\ndef main(): return f(B())\n',
                     B_RUN, "typed"),
    "an-annotated-local": Case("from app.models import B, build\ndef main():\n    x: B = build()\n"
                               "    return x.run()\n", B_RUN, "typed"),
    "a-declared-result": Case("from app.models import make\ndef main():\n    x = make()\n    return x.run()\n",
                              B_RUN, "typed"),
    "an-attribute-set-in-a-method": Case(
        "from app.models import B\nclass C:\n    def __init__(self): self.b = B()\n"
        "    def go(self): return self.b.run()\ndef main(): return C().go()\n", B_RUN, "typed"),
    "an-attribute-annotated-in-the-class": Case(
        "from app.models import B\nclass C:\n    b: B\n    def go(self): return self.b.run()\n"
        "def main():\n    c = C()\n    c.b = B()\n    return c.go()\n", B_RUN, "typed"),
    "a-function-of-a-repo-module": Case("from app import service\ndef main(): return service.run()\n",
                                        "app/service:run", "typed"),
}

# -- a scope trap: the binding a name refers to is the one CPython's scopes give it ---------------------------------
SCOPES = {
    "a-comprehension-variable": Case(
        "from app.models import A, B\ndef main():\n    x = A()\n    return [x.run() for x in [B()]][0]\n",
        B_RUN, "unknown", "app/models:A.run", reason="a comprehension's variable"),
    "a-class-body-does-not-enclose-its-methods": Case(
        "from app.models import A, B\nclass C:\n    x = A()\n    def go(self): return x.run()\nx = B()\n"
        "def main(): return C().go()\n", B_RUN, "typed", "app/models:A.run"),
    "a-closure": Case("from app.models import A, B\nx = A()\ndef main():\n    x = B()\n"
                      "    def inner(): return x.run()\n    return inner()\n", B_RUN, "typed", "app/models:A.run"),
    "a-global-bound-in-a-function": Case(
        "from app.models import A, B\ndef setup():\n    global x\n    x = B()\ndef other():\n    x = A()\n"
        "    return x\ndef main():\n    setup()\n    return x.run()\n", B_RUN, "typed", "app/models:A.run"),
    "a-global-rebinding-a-module-variable": Case(
        "from app.models import A, B\nx = A()\ndef setup():\n    global x\n    x = B()\n"
        "def main():\n    setup()\n    return x.run()\n", B_RUN, "unknown", "app/models:A.run",
        reason="bindings that disagree"),
    "a-nonlocal-rebinding": Case(
        "from app.models import A, B\ndef main():\n    x = B()\n    def inner():\n        nonlocal x\n"
        "        x = A()\n    inner()\n    return x.run()\n", "app/models:A.run", "unknown", B_RUN,
        reason="bindings that disagree"),
    "a-walrus-in-a-comprehension-binds-in-the-function": Case(
        "from app.models import A, B\nx = A()\ndef main():\n    [y for y in [0] if (x := B())]\n"
        "    return x.run()\n", B_RUN, "typed", "app/models:A.run"),
    "two-bindings-that-disagree": Case(
        "from app.models import A, B\ndef main(flag=True):\n    x = A()\n    if flag:\n        x = B()\n"
        "    return x.run()\n", B_RUN, "unknown", "app/models:A.run",
        reason="bindings that disagree"),
    "a-for-target": Case("from app.models import B\ndef main():\n    for x in [B()]:\n        return x.run()\n",
                         B_RUN, "unknown", reason="a for target"),
    "a-with-target": Case(
        "from app.models import A\nclass Session:\n    def run(self): pass\n    def __enter__(self): return A()\n"
        "    def __exit__(self, *exc): return False\ndef main():\n    with Session() as x:\n        return x.run()\n",
        "app/models:A.run", "unknown", "app/use:Session.run", reason="a with target"),
}

# -- what the declarations in sight do not decide, or decide is not the repo's ------------------------------------
UNDECIDED = {
    "a-container": Case("from app.models import B\ndef f(x: list[B]): return x.run()\n", None, "unknown", B_RUN,
                        reason="a builtin, or a name no statement of the file binds"),
    "a-union": Case("from typing import Union\nfrom app.models import A, B\ndef f(x: Union[A, B]): return x.run()\n"
                    "def main(): return f(B())\n", B_RUN, "unknown", "app/models:A.run",
                    reason="a union of several types"),
    "a-manager-of-an-external-base": Case(
        "from django.db import models\nclass Item(models.Model):\n    pass\nclass Repo:\n    def filter(self): pass\n"
        "def main(): return Item.objects.filter()\n", None, "unknown", method="filter",
        reason="an attribute a base outside the repo may give"),
    "an-attribute-of-an-external-base": Case(
        "from rest_framework.views import APIView\nfrom app.models import B\nclass C(APIView):\n"
        "    def go(self): return self.request.run()\nclass D:\n    def __init__(self): self.request = B()\n",
        None, "unknown", B_RUN, reason="an attribute a base outside the repo may give"),
    "an-external-base-ahead-in-the-mro": Case(
        "from threading import Thread\nfrom app.models import Base\nclass C(Thread, Base):\n"
        "    def go(self): return self.run()\ndef main(): return C().go()\n", "threading:Thread.run", "unknown",
        BASE_RUN, reason="a method a base outside the repo may give, ahead in the MRO"),
    "a-base-only-a-star-import-binds": Case(
        "from app.models import *\nclass C(Base):\n    pass\ndef main(): return C().run()\n", BASE_RUN, "unknown",
        reason="a name only a star import may bind"),
    "a-function-a-module-may-get-by-a-star-import": Case(
        "from app import everything\ndef main(): return everything.make()\n", "app/models:make", "unknown",
        method="make", reason="a name only a star import may bind"),
    "a-method-a-builtin-base-gives": Case(
        "class D(dict):\n    pass\ndef main(): return D().get('x')\n", None, "unknown", method="get",
        reason="a method a base outside the repo may give, ahead in the MRO"),
    "an-instance-of-an-external-class": Case(
        "from json import JSONDecoder\nclass Codec:\n    def decode(self, text): pass\ndef main():\n"
        '    d = JSONDecoder()\n    return d.decode("1")\n', "json/decoder:JSONDecoder.decode", "external",
        "app/use:Codec.decode", "decode", "a type of a package outside the repo"),
}
CASES = DECLARED | SCOPES | UNDECIDED

# the first function of the case's method name that CPython enters while `main()` runs
TRACE = """import sys
seen = []
def trace(frame, event, arg):
    if event == "call" and frame.f_code.co_name == sys.argv[1] and not seen:
        seen.append(frame.f_globals["__name__"].replace(".", "/") + ":" + frame.f_code.co_qualname)
sys.setprofile(trace)
from app.use import main
main()
sys.setprofile(None)
print(seen[0] if seen else "")
"""


def _write(root, files: dict[str, str]) -> None:
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)


def _repo(root, files: dict[str, str]) -> None:
    _write(root, {"pyproject.toml": PYPROJECT, "app/__init__.py": "", "app/models.py": MODELS,
                  "app/service.py": SERVICE, "app/everything.py": "from app.models import *\n", **files})


def _extract(root):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    repo = RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root))
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(repo)


def extracted(root, case: Case):
    """The extraction and the resolution of the case's repo."""
    _repo(root, {"app/use.py": case.use})
    return _extract(root)


def edges_of(res, rv, case: Case) -> set[tuple[str, str]]:
    """The targets and strategies of the edges of the case's calls of its method."""
    sym = {s.id: s for s in res.symbols}
    use = next(f.id for f in res.files if f.path == "app/use.py")
    return {(sym[e.callee_id].qualified_name, e.strategy) for e in rv.calls
            if use in (e.caller_id, getattr(sym.get(e.caller_id), "file_id", None))
            and (e.method or sym[e.callee_id].name) == case.method}


def _edges(root, case: Case) -> set[tuple[str, str]]:
    return edges_of(*extracted(root, case), case)


def typed_targets(edges: set[tuple[str, str]]) -> set[str]:
    """The methods the edges reach by type; an inherited edge reaches the type, not a method of the repo."""
    return {target for target, strategy in edges if strategy.removesuffix("-ambiguous") not in NAMED + INHERITED}


def _cases() -> list:
    return [pytest.param(c, id=i) for i, c in CASES.items()]


@pytest.mark.parametrize("case", [p for p in _cases() if p.values[0].runs])
def test_cpython_runs_the_method_the_case_names(tmp_path, case):
    _repo(tmp_path, {"app/use.py": case.use})
    ran = subprocess.run([sys.executable, "-c", TRACE, case.method], cwd=tmp_path, capture_output=True, text=True,
                         check=True).stdout.strip()
    assert ran == case.runs != case.wrong


@pytest.mark.parametrize("case", [p for p in _cases() if p.values[0].wrong])
def test_a_name_never_takes_the_type_of_a_binding_not_its_own(tmp_path, case):
    assert case.wrong not in typed_targets(_edges(tmp_path, case))


@pytest.mark.parametrize("case", [p for p in _cases() if p.values[0].answer == "unknown"
                                  and (p.values[0].runs or "").startswith("app/")])
def test_an_undecided_receiver_is_found_by_name(tmp_path, case):
    edges = _edges(tmp_path, case)
    assert edges and {strategy.removesuffix("-ambiguous") for _, strategy in edges} <= set(NAMED)


@pytest.mark.parametrize("case", _cases())
def test_the_scope_index_classifies_every_name_of_a_case_as_cpython(case):
    assert compare(case.use.encode()) == []
