"""What a dispatching call may run, read from the graph: its target, and each method that `OVERRIDES` the target on a
type of the call's `receivers`, or on any when the call has none. Python's is what CPython runs on every class of the
case at or below the receiver's annotated class; C#'s follows the language's rules, a sibling's override and a
narrower interface's implementer left out."""

import contextlib
import io
import subprocess
import sys
from pathlib import Path

PY = """class Base:
    def save(self):
        return "Base"


class Left(Base):
    def save(self):
        return "Left"


class LeftLeaf(Left):
    pass


class LeftMost(Left):
    def save(self):
        return "LeftMost"


class Right(Base):
    def save(self):
        return "Right"


class RightLeaf(Right):
    pass


class Mixin:
    def save(self):
        return "Mixin"


class Both(Mixin, RightLeaf):
    pass


def run(base: Base, left: Left, leaf: LeftLeaf, right: Right, rleaf: RightLeaf):
    base.save()
    left.save()
    leaf.save()
    right.save()
    rleaf.save()
"""
RUNS = """import importlib, inspect, sys
m = importlib.import_module("app.use")
classes = [c for c in vars(m).values() if inspect.isclass(c) and c.__module__ == "app.use"]
for name in sys.argv[1:]:
    t = vars(m)[name]
    print(name, *sorted({next(k for k in d.__mro__ if "save" in vars(k)).__qualname__ + ".save"
                         for d in classes if issubclass(d, t)}))
"""
CS = """namespace App;

public class Root { public virtual void Save() { } }
public class Left : Root { public override void Save() { } }
public class Right : Root { public override void Save() { } }
public class LeftLeaf : Left { }
public class LeftMost : Left { public override void Save() { } }

public interface IStore { void Put(); }
public interface IFiles : IStore { }
public class Disk : IFiles { public void Put() { } }
public class Memory : IStore { public void Put() { } }

public class Use
{
    public void Run(Root root, LeftLeaf leaf, IFiles files, IStore store)
    {
        root.Save();
        leaf.Save();
        files.Put();
        store.Put();
    }
}
"""


def _may_run(root: Path, files: dict[str, str], caller: str, prefix: str) -> dict[int, set[str]]:
    """Each line of `caller` with a dispatching call: what the graph says it may run, by the target's `receiver-type`
    edge."""
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root)),
                                      convs=[])
    q = {s.id: s.qualified_name.removeprefix(prefix) for s in res.symbols}
    overrides = [e for e in rv.hierarchy if e.kind == "OVERRIDES"]
    out = {}
    for c in rv.calls:
        if q[c.caller_id] == caller and c.virtual and c.strategy == "receiver-type":
            out[c.line] = {q[c.callee_id]} | {q[e.source_id] for e in overrides if e.target_id == c.callee_id
                                              and (not c.receivers or set(c.receivers) & set(e.receivers))}
    return out


def test_python_a_call_may_run_what_cpython_runs_on_its_receivers_classes(tmp_path):
    files = {"pyproject.toml": '[project]\nname = "app"\n', "app/__init__.py": "", "app/use.py": PY}
    graph = _may_run(tmp_path, files, "run", "app/use:")
    receivers = ["Base", "Left", "LeftLeaf", "Right", "RightLeaf"]
    ran = subprocess.run([sys.executable, "-c", RUNS, *receivers], cwd=tmp_path, capture_output=True, text=True,
                         check=True).stdout
    cpython = {name: set(found) for name, *found in (line.split() for line in ran.splitlines())}
    first = PY.splitlines().index("    base.save()") + 1
    assert {receivers[line - first]: found for line, found in graph.items()} == cpython
    assert cpython["LeftLeaf"] == {"Left.save"}                         # not its sibling's override
    assert cpython["RightLeaf"] == {"Right.save", "Mixin.save"}         # a mixin a subclass puts first


def test_csharp_a_call_may_run_the_overrides_on_its_receivers_types(tmp_path):
    files = {"App.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>\n', "Model.cs": CS}
    assert _may_run(tmp_path, files, "Use.Run", "App.") == {
        18: {"Root.Save", "Left.Save", "Right.Save", "LeftMost.Save"},
        19: {"Left.Save"},                              # a LeftLeaf runs no other class's override
        20: {"IStore.Put", "Disk.Put"},                 # only Disk is an IFiles
        21: {"IStore.Put", "Disk.Put", "Memory.Put"},
    }
