"""`OVERRIDES`: a method a dispatching call to another may run instead, on an instance of a type of the repo. Python's
are what CPython's `__mro__` finds first for each class of the case, which runs here; C#'s follow the language's
`override`, `new`, `static` and interface implementation, matched by name and number of parameters."""

import contextlib
import io
import subprocess
import sys
from pathlib import Path

PY = """class Base:
    def save(self):
        return "Base"

    def load(self):
        return "Base"


class Audit:
    def save(self):
        return "Audit"


class Stamp(Base):
    def save(self):
        return "Stamp"

    def load(self):
        return "Stamp"


class Doc(Audit, Stamp):
    pass


class Note(Audit, Base):
    def load(self):
        return "Note"


class Twice(Base):
    def save(self):
        return "first"

    def save(self):
        return "Twice"


class After(Twice):
    pass
"""
RUNS = """import importlib, inspect
m = importlib.import_module("app.use")
for d in [c for c in vars(m).values() if inspect.isclass(c) and c.__module__ == "app.use"]:
    for a in [a for a in d.__mro__[1:] if a.__module__ == "app.use"]:
        for name, f in [(n, f) for n, f in vars(a).items() if inspect.isfunction(f)]:
            run = next(k for k in d.__mro__ if name in vars(k))
            g = vars(run)[name]
            if run is not a and inspect.isfunction(g):
                print(f"app/use:{run.__qualname__}.{name}", g.__code__.co_firstlineno,
                      f"app/use:{a.__qualname__}.{name}", f.__code__.co_firstlineno)
"""
CS = """namespace App;

public interface IRead { int Get(); }
public interface IRepo : IRead { }

public class Root : IRepo
{
    public virtual int Get() => 0;
    public virtual int Get(int id) => id;
    public virtual void Save() { }
    public virtual void Load(int id) { }
    public static void Make() { }
}

public class Mid : Root
{
    public override int Get() => 1;
    public new virtual void Save() { }
    public virtual void Load(string key) { }
    public static void Make() { }
}

public class Leaf : Mid
{
    public override int Get(int id) => 2;
    public override void Save() { }
    public override void Load(int id) { }
}

public class Plain : IRead
{
    int IRead.Get() => 3;
}
"""


def _overrides(root: Path, files: dict[str, str]) -> set[tuple[str, int, str, int]]:
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root)),
                                      convs=[])
    sym = {s.id: s for s in res.symbols}
    return {(sym[e.source_id].qualified_name, sym[e.source_id].line_start, sym[e.target_id].qualified_name,
             sym[e.target_id].line_start) for e in rv.hierarchy if e.kind == "OVERRIDES"}


def test_python_overrides_are_what_cpython_runs_for_each_class(tmp_path):
    files = {"pyproject.toml": '[project]\nname = "app"\n', "app/__init__.py": "", "app/use.py": PY}
    edges = _overrides(tmp_path, files)
    ran = subprocess.run([sys.executable, "-c", RUNS], cwd=tmp_path, capture_output=True, text=True, check=True).stdout
    cpython = {(a, int(la), b, int(lb)) for a, la, b, lb in (line.split() for line in ran.splitlines())}
    assert edges == cpython
    assert ("app/use:Audit.save", 10, "app/use:Stamp.save", 15) in cpython        # a mixin before a class it does not extend
    assert ("app/use:Twice.save", 35, "app/use:Base.save", 2) in cpython          # the later definition of a name


def test_csharp_overrides_follow_override_new_static_and_interfaces(tmp_path):
    assert _overrides(tmp_path, {"App.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>\n', "Model.cs": CS}) == {
        ("App.Root.Get", 8, "App.IRead.Get", 3),
        ("App.Mid.Get", 17, "App.Root.Get", 8),
        ("App.Mid.Get", 17, "App.IRead.Get", 3),                # through the base class that names the interface
        ("App.Leaf.Get", 25, "App.Root.Get", 9),                # by the number of parameters, past a class without it
        ("App.Leaf.Save", 26, "App.Mid.Save", 18),              # `new` hides Root.Save from the classes below Mid
        ("App.Leaf.Load", 27, "App.Root.Load", 11),             # Mid's Load of one parameter may be an overload
        ("App.Leaf.Load", 27, "App.Mid.Load", 19),              # and the number of parameters cannot tell which
        ("App.Plain.Get", 32, "App.IRead.Get", 3),              # an explicit implementation
    }
