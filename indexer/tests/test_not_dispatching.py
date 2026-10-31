"""A call the language sends to one method by name (C# `base.M()`, Python `super().m()`) reaches that method only: never
the implementation a dispatching call would, and never a homonym found by name. Python's targets are what CPython runs
for each class of the fixture; past a base outside the repo, which may bind the name first, there is none."""

import ast
import contextlib
import io
import subprocess
import sys

BASE_CALL = {
    "App.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
    "Finders.cs": """namespace App;

public class Root { public virtual int Find() => 0; }

public class Site : Root
{
    public override int Find()
    {
        return base.Find();
    }
}
""",
}
SEVERAL_BASES = """class A:
    def run(self):
        return "A"


class B:
    def run(self):
        return "B"


class C(A, B):
    def run(self):
        return "C+" + super().run()


RUNS = {"C": C().run()}
"""
MIXINS = """class Base:
    def save(self):
        return "Base"


class Audit:
    def save(self):
        return "Audit+" + super().save()


class Stamp(Base):
    def save(self):
        return "Stamp+" + super().save()


class Doc(Audit, Stamp):
    pass


class Note(Audit, Base):
    pass


RUNS = {"Doc": Doc().save(), "Note": Note().save(), "Stamp": Stamp().save()}
"""
OUTSIDE = """import json


class Local:
    def default(self, o):
        return "Local"


class Mixin:
    def default(self, o):
        return "Mixin+" + super().default(o)


class Encoder(Mixin, json.JSONEncoder, Local):
    pass


def runs():
    try:
        return Encoder().default(1)
    except TypeError:
        return "Mixin+JSONEncoder"


RUNS = {"Encoder": runs()}
"""


def _resolved(root, files):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root)),
                                   convs=[])


def _python(root, source):
    return _resolved(root, {"pyproject.toml": '[project]\nname = "app"\n', "app/__init__.py": "", "app/use.py": source})


def _targets(res, rv, line: int) -> set[tuple[str, str, bool]]:
    q = {s.id: s.qualified_name for s in res.symbols}
    return {(q[c.callee_id], c.strategy, c.virtual) for c in rv.calls if c.line == line}


def _cpython(source: str) -> dict[str, str]:
    ran = subprocess.run([sys.executable, "-c", source + "\nprint(repr(RUNS))\n"], capture_output=True, text=True,
                         check=True)
    return ast.literal_eval(ran.stdout)


def _after(runs: dict[str, str], cls: str) -> set[str]:
    """The class each chain of calls runs right after `cls`'s method."""
    return {chain[chain.index(cls) + 1] for chain in (r.split("+") for r in runs.values()) if cls in chain[:-1]}


def test_a_call_on_base_reaches_the_bases_method_only(tmp_path):
    assert _targets(*_resolved(tmp_path, BASE_CALL), 9) == {("App.Root.Find", "receiver-type", False)}


def test_super_in_a_class_of_several_bases_reaches_what_cpython_runs(tmp_path):
    runs = _cpython(SEVERAL_BASES)
    assert _after(runs, "C") == {"A"}
    assert _targets(*_python(tmp_path, SEVERAL_BASES), 13) == {("app/use:A.run", "receiver-type", False)}


def test_super_in_a_mixin_reaches_what_follows_it_in_each_classs_mro(tmp_path):
    runs = _cpython(MIXINS)
    assert _after(runs, "Audit") == {"Stamp", "Base"} and _after(runs, "Stamp") == {"Base"}
    res, rv = _python(tmp_path, MIXINS)
    assert _targets(res, rv, 8) == {("app/use:Stamp.save", "receiver-type-ambiguous", False),
                                    ("app/use:Base.save", "receiver-type-ambiguous", False)}
    assert _targets(res, rv, 13) == {("app/use:Base.save", "receiver-type", False)}


def test_super_past_a_base_outside_the_repo_reaches_nothing(tmp_path):
    assert _after(_cpython(OUTSIDE), "Mixin") == {"JSONEncoder"}
    assert _targets(*_python(tmp_path, OUTSIDE), 11) == set()
