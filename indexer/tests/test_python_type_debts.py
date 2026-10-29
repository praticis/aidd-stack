"""Python's types, where the resolver still reads a receiver wrongly. Each case states the right answer, the method
CPython runs for its call, and is a strict xfail with the reason: when the resolver learns it, the case passes, the
xfail fails the suite, and the mark has to go."""

import subprocess
import sys

import pytest

from test_python_types import TRACE, Case, edges_of, extracted

DEEPCOPY = Case("from copy import deepcopy\nfrom app.models import B\ndef main(): return deepcopy(B()).run()\n",
                "app/models:B.run", "unknown")


def case(id, given: Case, why):
    return pytest.param(given, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


CASES = [
    case("a-function-outside-the-repo-may-return-a-value-of-the-repo", DEEPCOPY,
         "a call of a name outside the repo is taken for an instance of it"),
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
