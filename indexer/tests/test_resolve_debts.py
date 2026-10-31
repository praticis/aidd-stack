"""The resolver's calls that do not dispatch and the types' bases, where it still gives a target the code does not
name: a call on `base` or `super()` runs a method of an ancestor of the caller's class, never the caller's own, and a
base is the type the code names. Each case states the right answer and is a strict xfail with the reason: when the
resolver learns it, the case passes, the xfail fails the suite, and the mark has to go."""

import contextlib
import io
import subprocess
import sys

import pytest

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
SUPER_CALL = {
    "pyproject.toml": '[project]\nname = "app"\n',
    "app/__init__.py": "",
    "app/use.py": """class A:
    def run(self):
        return "A"


class B:
    def run(self):
        return "B"


class C(A, B):
    def run(self):
        return super().run()


def main():
    return C().run()
""",
}
ONE_FILE = {
    "App.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
    "Handlers.cs": """namespace App;

public interface IHandler { }

public interface IHandler<T> : IHandler { }

public class Handler : IHandler<int> { }
""",
}


def case(id, files, why):
    return pytest.param(files, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


BASE = [case("a-call-on-base-reaches-no-implementation-of-the-callers-class", BASE_CALL,
             "the implementation of the base class's single subclass is looked for, though `base.` never dispatches")]
SUPER = [case("a-call-on-super-reaches-an-ancestors-method-and-never-the-callers", SUPER_CALL,
              "a `super()` the type index does not decide is found by name among every class's methods")]
BASES = [case("two-types-of-one-name-in-one-file-are-no-base-of-each-other", ONE_FILE,
              "a file's type facts keep one of two types of one name, so both take its bases and every type that "
              "names either reaches both")]


def _resolved(root, files):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root)),
                                   convs=[])


def _targets(res, rv, line: int) -> set[str]:
    q = {s.id: s.qualified_name for s in res.symbols}
    return {q[c.callee_id] for c in rv.calls if c.line == line}


@pytest.mark.parametrize("files", BASE)
def test_a_call_on_base_reaches_the_bases_method_only(tmp_path, files):
    assert _targets(*_resolved(tmp_path, files), 9) == {"App.Root.Find"}


def test_cpython_runs_the_first_bases_method_for_super():
    ran = subprocess.run([sys.executable, "-c", SUPER_CALL["app/use.py"] + "\nprint(main())\n"], capture_output=True,
                         text=True, check=True).stdout.strip()
    assert ran == "A"


@pytest.mark.parametrize("files", SUPER)
def test_a_call_on_super_reaches_ancestors_methods_only(tmp_path, files):
    found = _targets(*_resolved(tmp_path, files), 13)
    assert "app/use:A.run" in found and found <= {"app/use:A.run", "app/use:B.run"}


@pytest.mark.parametrize("files", BASES)
def test_a_type_reaches_only_the_base_it_names(tmp_path, files):
    res, rv = _resolved(tmp_path, files)
    line = {s.id: s.line_start for s in res.symbols}
    edges = {(line[e.source_id], e.kind, line[e.target_id]) for e in rv.hierarchy}
    assert not edges & {(3, "EXTENDS", 5), (7, "IMPLEMENTS", 3)}
