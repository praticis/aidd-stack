"""Python's types, where the resolver or the HTTP scanner still reads a receiver wrongly. Each case states the right
answer, the method CPython runs for its call, that no method of the repo does where a package's method serves it, the
client wrapper the call goes through, or the override of the repo a call to a package's method may run, and is a strict
xfail with the reason: when the index learns it, the case passes, the xfail fails the suite, and the mark has to go."""

import subprocess
import sys

import pytest

from test_python_types import TRACE, Case, edges_of, extracted
from test_python_wrappers import indexed

DEEPCOPY = Case("from copy import deepcopy\nfrom app.models import B\ndef main(): return deepcopy(B()).run()\n",
                "app/models:B.run", "unknown")
MANAGER = Case("from django.db import models\nclass Item(models.Model):\n    pass\nclass Repo:\n    def filter(self): pass\n"
               "def main(): return Item.objects.filter()\n", None, "external", method="filter")
LOCAL_CLASS = {"app/use.py": "import httpx\n\n\ndef local():\n    class Inner:\n        def _get(self, path):\n"
                             "            return httpx.get(\"http://in\" + path)\n\n        def go(self):\n"
                             "            return self._get(\"/v1/inner\")\n\n    return Inner\n"}


def case(id, given: Case, why):
    return pytest.param(given, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


CASES = [
    case("a-function-outside-the-repo-may-return-a-value-of-the-repo", DEEPCOPY,
         "a call of a name outside the repo is taken for an instance of it"),
]
OUTSIDE = [
    case("a-django-model-manager-without-one-of-the-repo-serves-no-method-of-it", MANAGER,
         "an attribute a base outside the repo may give is unknown, so its method is found by name"),
]
OUTSIDE_METHOD = {"app/views.py": "from rest_framework.generics import GenericAPIView\n\n\n"
                                  "class Base(GenericAPIView):\n    def fields(self):\n"
                                  "        return self.get_serializer_class()\n\n\n"
                                  "class Prefix(Base):\n    def get_serializer_class(self):\n        return None\n"}
OVERRIDDEN = [
    case("an-override-of-a-method-a-base-outside-the-repo-declares-meets-its-calls", OUTSIDE_METHOD,
         "the method a base outside the repo declares is no symbol, so a call to it has no edge an override can meet"),
]
WRAPPED = [
    case("a-class-a-function-holds-reaches-its-own-wrapper", LOCAL_CLASS,
         "the type index has no name for a class a function holds, so its instance has no class"),
]


@pytest.mark.parametrize("given", [DEEPCOPY])
def test_cpython_runs_the_method_the_case_names(tmp_path, given):
    extracted(tmp_path, given)
    ran = subprocess.run([sys.executable, "-c", TRACE, given.method], cwd=tmp_path, capture_output=True, text=True,
                         check=True).stdout.strip()
    assert ran == given.runs


@pytest.mark.parametrize("given", CASES)
def test_a_call_reaches_the_method_cpython_runs(tmp_path, given):
    assert given.runs in {target for target, _ in edges_of(*extracted(tmp_path, given), given)}


@pytest.mark.parametrize("given", OUTSIDE)
def test_a_call_a_package_serves_reaches_no_method_of_the_repo(tmp_path, given):
    assert not {target for target, _ in edges_of(*extracted(tmp_path, given), given) if target.startswith("app/")}


@pytest.mark.parametrize("files", WRAPPED)
def test_a_call_reaches_the_wrapper_of_a_class_a_function_holds(tmp_path, files):
    res, _ = indexed(tmp_path, files)
    assert {(c.method, c.path) for c in res.http_calls} == {("GET", "/v1/inner")}


@pytest.mark.parametrize("files", OVERRIDDEN)
def test_a_call_to_a_packages_method_meets_the_override_of_the_repo(tmp_path, files):
    _, rv = indexed(tmp_path, files)
    called = {c.callee_id for c in rv.calls if c.line == 6 and c.virtual}
    assert called & {e.target_id for e in rv.hierarchy
                     if e.kind == "OVERRIDES" and e.source_id.endswith(":Prefix.get_serializer_class#method")}
