"""Python's types, where the resolver still reads a receiver wrongly. Each case states the right answer, the method
CPython runs for its call or, where a package's method serves it, that no method of the repo does, and is a strict
xfail with the reason: when the resolver learns it, the case passes, the xfail fails the suite, and the mark has to
go."""

import subprocess
import sys

import pytest

from test_python_types import TRACE, Case, edges_of, extracted

DEEPCOPY = Case("from copy import deepcopy\nfrom app.models import B\ndef main(): return deepcopy(B()).run()\n",
                "app/models:B.run", "unknown")
MANAGER = Case("from django.db import models\nclass Item(models.Model):\n    pass\nclass Repo:\n    def filter(self): pass\n"
               "def main(): return Item.objects.filter()\n", None, "external", method="filter")


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
