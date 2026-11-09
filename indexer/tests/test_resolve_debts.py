"""What a C# type's name stands for, where the resolver still takes one type for another: two types of one name in one
file (`Populator` and `Populator<T>`), and a type written with a namespace outside the repo whose simple name a type of
the repo has. A call on `base` shows both, reaching the caller's own method. And a call on an interface, which reaches
its single implementer by an edge of its own as well as by the implementer's `OVERRIDES`. And a call found by name,
which draws its homonyms from every language of the repo, a JS function reached from Go or Python code. Each case
states the right answer and is a strict xfail with the reason: when the resolver learns it, the case passes, the xfail
fails the suite, and the mark has to go."""

import contextlib
import io

import pytest

CSPROJ = '<Project Sdk="Microsoft.NET.Sdk"></Project>\n'
ONE_NAME = {
    "App.csproj": CSPROJ,
    "Populators.cs": """namespace App;

public abstract class Populator
{
    public virtual bool IsRegistered() => true;
}

public abstract class Populator<T> : Populator
{
    public override bool IsRegistered()
    {
        return base.IsRegistered();
    }
}
""",
}
PACKAGE_NAME = {
    "App.csproj": CSPROJ,
    "Converters.cs": """namespace App.Json;

public class MoneyJsonConverter : Pkg.Json.MoneyJsonConverter
{
    public override object ReadJson()
    {
        return base.ReadJson();
    }
}

public class Reader
{
    public object Read(Pkg.Json.MoneyJsonConverter converter)
    {
        return converter.ReadJson();
    }
}
""",
}

SINGLE_IMPLEMENTER = {
    "App.csproj": CSPROJ,
    "Store.cs": """namespace App;

public interface IStore { void Put(); }
public class Disk : IStore { public void Put() { } }

public class Use
{
    public void Run(IStore store)
    {
        store.Put();
    }
}
""",
}


GO_TO_JS = {
    "go.mod": "module example.com/app\n\ngo 1.22\n",
    "server.go": 'package app\n\nimport "net/http"\n\nfunc Handle(w http.ResponseWriter) { w.Header() }\n',
    "web/bundle.js": "function Header() { return 1 }\nmodule.exports = { Header }\n",
}
PYTHON_TO_JS = {
    "app/use.py": "def main(w):\n    w.header()\n",
    "web/bundle.js": "function header() { return 1 }\nmodule.exports = { header }\n",
}


def case(id, files, lines, expected, why):
    return pytest.param(files, lines, expected, id=id, marks=pytest.mark.xfail(strict=True, reason=why))


CASES = [
    case("a-go-call-reaches-no-symbol-of-another-language", GO_TO_JS, (5,), set(),
         "finds a call by name among the homonyms of every language of the repo, and a JS function is no Go callee"),
    case("a-python-call-reaches-no-symbol-of-another-language", PYTHON_TO_JS, (2,), set(),
         "finds a call by name among the homonyms of every language of the repo, and a JS function is no Python callee"),
    case("a-call-on-one-of-two-types-of-one-name-reaches-that-types-method", ONE_NAME, (12,), {5},
         "a file's type facts keep one of two types of one name, and their methods share a qualified name"),
    case("a-type-written-with-a-namespace-outside-the-repo-is-not-the-repos", PACKAGE_NAME, (7, 15), set(),
         "reads a written type by its simple name, which the repo's own type has"),
    case("a-call-on-an-interface-reaches-its-single-implementer-by-the-dispatch-alone", SINGLE_IMPLEMENTER, (10,), {3},
         "a call on an interface also links to its single implementer, which the implementer's OVERRIDES reaches"),
]


def _resolved(root, files):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root)),
                                   convs=[])


@pytest.mark.parametrize("files,lines,expected", CASES)
def test_a_call_reaches_the_method_of_the_type_the_code_names(tmp_path, files, lines, expected):
    res, rv = _resolved(tmp_path, files)
    declared = {s.id: s.line_start for s in res.symbols}
    assert {declared[c.callee_id] for c in rv.calls if c.line in lines} == expected
