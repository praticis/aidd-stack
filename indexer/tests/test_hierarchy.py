"""`EXTENDS` and `IMPLEMENTS`: the types of the repo a type names as its direct bases, as its language reads them, and
the calls whose method the object's class does not choose (`virtual: false`). Python's edges are the bases CPython
gives each class of the case, which runs here; C#'s close into the ancestry the resolver walks for a call."""

import contextlib
import io
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

PY = {
    "pyproject.toml": '[project]\nname = "app"\n',
    "app/__init__.py": "",
    "app/models.py": "class Base:\n    def run(self): pass\n\n\nclass Other:\n    pass\n",
    "app/stars.py": "from app.models import *\n\n\nclass Starred(Base):\n    pass\n",
    "app/use.py": """from threading import Thread
from app import models
from app.models import Base, Other


class One(Base):
    def run(self):
        super().run()
        self.run()


class Two(Base, Other):
    pass


class Package(Thread):
    pass


class Mixed(Base, Thread):
    pass


class Outer:
    class Inner(Base):
        pass


class FromInner(Outer.Inner):
    pass


class ByModule(models.Base):
    pass
""",
}
BASES = """import importlib, inspect, sys
for name in sys.argv[1:]:
    todo = [c for c in vars(importlib.import_module(name)).values() if inspect.isclass(c) and c.__module__ == name]
    for c in todo:
        todo += [n for n in vars(c).values() if inspect.isclass(n) and n.__qualname__.startswith(c.__qualname__ + ".")]
        for b in c.__bases__:
            if b.__module__.startswith("app."):
                print(f"{name.replace('.', '/')}:{c.__qualname__} {b.__module__.replace('.', '/')}:{b.__qualname__}")
"""
CS = {
    "App.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
    "Model.cs": """namespace App;

public interface IRead { void Get(); }
public interface IRepo : IRead { }
public abstract class BaseRepo { public virtual void Get() { } }
public class Repo : BaseRepo, IRepo
{
    public override void Get()
    {
        base.Get();
        this.Get();
    }
}
public struct Point : IRead { public void Get() { } }
public record BaseRecord;
public record Record : BaseRecord;
public class BaseOf<T> { }
public class Of<T> : BaseOf<T> { }
public class Failure : System.Exception { }
""",
    "Part1.cs": "namespace App;\n\npublic partial class Service : BaseRepo { }\n",
    "Part2.cs": "namespace App;\n\npublic partial class Service : IRepo { }\n",
}
GO = {
    "go.mod": "module example.com/app\n\ngo 1.22\n",
    "app.go": """package app

type Base struct{}

func (Base) Run() {}

type Child struct {
	Base
}

type Reader interface{ Read() }

type ReadCloser interface {
	Reader
	Close()
}
""",
}


def _write(root: Path, files: dict[str, str]) -> Path:
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    return root


def _resolved(root: Path):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name=root.name, ref="main", commit_sha="x", root=str(root)),
                                   convs=[])


def _edges(res, rv) -> set[tuple[str, str, str]]:
    q = {s.id: s.qualified_name for s in res.symbols}
    return {(q[e.source_id], e.kind, q[e.target_id]) for e in rv.hierarchy}


def _calls(res, rv, line: int) -> set[tuple[str, bool]]:
    q = {s.id: s.qualified_name for s in res.symbols}
    return {(q[c.callee_id], c.virtual) for c in rv.calls if c.line == line}


def test_python_edges_are_the_bases_cpython_gives(tmp_path):
    root = _write(tmp_path / "py", PY)
    ran = subprocess.run([sys.executable, "-c", BASES, "app.use", "app.stars"], cwd=root, capture_output=True,
                         text=True, check=True).stdout.split("\n")
    cpython = {tuple(line.split()) for line in ran if line}
    edges = _edges(*_resolved(root))
    assert {(source, target) for source, _, target in edges} == cpython
    assert ("app/use:Mixed", "app/models:Base") in cpython and not any(s == "app/use:Package" for s, _ in cpython)
    assert {kind for _, kind, _ in edges} == {"EXTENDS"}


def test_a_call_on_super_does_not_dispatch_and_one_on_self_may(tmp_path):
    res, rv = _resolved(_write(tmp_path / "py", PY))
    assert _calls(res, rv, 8) == {("app/models:Base.run", False)}
    assert _calls(res, rv, 9) == {("app/use:One.run", True)}


def test_csharp_types_extend_classes_and_interfaces_and_implement_interfaces(tmp_path):
    assert _edges(*_resolved(_write(tmp_path / "cs", CS))) == {
        ("App.IRepo", "EXTENDS", "App.IRead"),
        ("App.Repo", "EXTENDS", "App.BaseRepo"),
        ("App.Repo", "IMPLEMENTS", "App.IRepo"),
        ("App.Point", "IMPLEMENTS", "App.IRead"),
        ("App.Record", "EXTENDS", "App.BaseRecord"),
        ("App.Of", "EXTENDS", "App.BaseOf"),
        ("App.Service", "EXTENDS", "App.BaseRepo"),            # the bases of a partial class's parts are the class's
        ("App.Service", "IMPLEMENTS", "App.IRepo"),
    }


def test_a_call_on_base_does_not_dispatch_and_one_on_this_may(tmp_path):
    res, rv = _resolved(_write(tmp_path / "cs", CS))
    assert _calls(res, rv, 10) == {("App.BaseRepo.Get", False)}
    assert _calls(res, rv, 11) == {("App.Repo.Get", True)}


@pytest.mark.parametrize("root", [FIXTURES / "csharp-receiver-types", FIXTURES / "csharp-praticis-todos",
                                  Path(__file__).parent / "mcp_it" / "accounts"], ids=lambda p: p.name)
def test_the_closure_of_a_csharp_types_edges_is_the_ancestry_the_resolver_walks(root):
    from aidd_indexer import languages
    from aidd_indexer.cli import extract_tree
    from aidd_indexer.core.model import RepoInfo
    from aidd_indexer.core.resolve import TYPE_KINDS, Resolver
    with contextlib.redirect_stderr(io.StringIO()):
        res, extractors = extract_tree(RepoInfo(tenant="t", name=root.name, ref="main", commit_sha="x", root=str(root)))
        resolver = Resolver(res, extractors)
        rv = resolver.run()
    up: dict[str, set[str]] = {}
    for source, _, target in _edges(res, rv):
        up.setdefault(source, set()).add(target)
    assert up
    csharp = languages.by_id("csharp")
    for t in {s.qualified_name for s in res.symbols if s.kind in TYPE_KINDS}:
        closure, todo = set(), list(up.get(t, ()))
        while todo:
            if (b := todo.pop()) not in closure:
                closure.add(b)
                todo += up.get(b, ())
        assert closure == set(csharp.supertypes(resolver.ctx, t)), t


def test_go_embedding_is_no_base(tmp_path):
    _, rv = _resolved(_write(tmp_path / "go", GO))
    assert rv.hierarchy == []


def test_a_call_dispatches_unless_the_language_sends_it_to_a_base_by_name():
    from aidd_indexer import languages
    from aidd_indexer.core.model import CallInfo
    from aidd_indexer.languages.python.forms import SUPER

    def call(receiver, **typed):
        return CallInfo("c", "m", receiver, 1, "f", **typed)
    python, csharp = languages.by_id("python"), languages.by_id("csharp")
    assert not python.dispatches(call("super()", receiver_type="super:app/use:One"))
    assert python.dispatches(call("super().x", receiver_type="super:app/use:One", receiver_path=("x",)))
    assert not python.dispatches(call("super(One, self)", receiver_unknown=SUPER.reason))
    assert python.dispatches(call("super(One, self).x", receiver_unknown=SUPER.reason))
    assert python.dispatches(call("self", receiver_type="app/use:One"))
    assert not csharp.dispatches(call("base"))
    assert csharp.dispatches(call("base.Inner")) and csharp.dispatches(call("this")) and csharp.dispatches(call(None))
    assert languages.by_id("go").dispatches(call("s"))
