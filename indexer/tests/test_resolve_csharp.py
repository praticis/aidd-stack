"""Call resolution in C#: receiver types from fields/properties/locals, inherited members
from in-repo bases, and interface -> unique implementer."""
from __future__ import annotations

import contextlib
import io
from pathlib import Path

FIX = Path(__file__).parent / "fixtures" / "csharp-receiver-types"


def _edges():
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    repo = RepoInfo(tenant="t", name=FIX.name, ref="main", commit_sha="x", root=str(FIX))
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(repo)
    sym = {s.id: s for s in res.symbols}
    out: dict[tuple[int, str], list[tuple[str, str]]] = {}
    for e in rv.calls:
        caller = sym.get(e.caller_id)
        if caller is not None and caller.name == "FindByIdAsync":
            out.setdefault((e.line, sym[e.callee_id].name), []).append((sym[e.callee_id].qualified_name, e.strategy))
    return out


def test_interface_field_links_to_interface_and_unique_implementer():
    e = _edges()[(18, "FindByIdAsync")]
    assert ("Shop.Api.Queries.IAccountQuery.FindByIdAsync", "receiver-type") in e
    assert ("Shop.Api.Infra.AccountReadRepository.FindByIdAsync", "receiver-type-impl") in e
    assert not any(q.endswith("AccountsController.FindByIdAsync") for q, _ in e)      # no self-call by homonym


def test_explicit_impl_of_another_interface_is_not_a_target():
    e = _edges()
    assert (22, "FindByIdAsync") not in e                      # `_accounts.FindByIdAsync` (IAccountReadRepository): no edge at all
    assert e[(18, "FindByIdAsync")] and all("IAccountQuery" in q or "AccountReadRepository" in q for q, _ in e[(18, "FindByIdAsync")])


def test_property_and_inherited_base_member():
    assert _edges()[(19, "CountAsync")] == [("Shop.Api.Infra.BaseReadRepository.CountAsync", "receiver-type")]


def test_services_resolved_from_the_container_and_closures():
    """`var q = provider.GetRequiredService<T>()`, `GetRequiredService<T>().M()` and a lambda using a local
    of the enclosing method all know the receiver's type (validators resolve repositories this way)."""
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    repo = RepoInfo(tenant="t", name=FIX.name, ref="main", commit_sha="x", root=str(FIX))
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(repo)
    sym = {s.id: s for s in res.symbols}
    got = {(e.line, sym[e.callee_id].qualified_name, e.strategy) for e in rv.calls
           if e.caller_id in sym and sym[e.caller_id].name == "Lookup" and sym[e.callee_id].name == "FindByIdAsync"}
    assert got == {(n, q, s) for n in (31, 32) for q, s in (("Shop.Api.Queries.IAccountQuery.FindByIdAsync", "receiver-type"),
                                                          ("Shop.Api.Infra.AccountReadRepository.FindByIdAsync", "receiver-type-impl"))}


def test_local_new_picks_the_right_homonym():
    assert _edges()[(21, "Describe")] == [("Shop.Api.Infra.GroupReadRepository.Describe", "receiver-type")]


THIS_BASE = """namespace Shop.Api.Infra;

public class TodoReadRepository : BaseReadRepository<TodoModel, Guid>, ITodoReadRepository
{
    public bool Exists(string name) => true;

    public bool NotExists(string name) => !this.Exists(name);

    public override Task<TodoModel?> FindByIdAsync(Guid id, CancellationToken ct) => base.FindByIdAsync(id, ct);
}
"""


def test_this_and_base_calls(tmp_path: Path):
    """`this.X()` / `base.X()` are call sites (the receivers are anonymous tokens in the grammar); a
    `base.X()` whose base type lives in a package resolves to nothing — never to the override itself."""
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    root = tmp_path / "shop"
    (root / "src/Shop.Api/Infra").mkdir(parents=True)
    (root / "src/Shop.Api/Shop.Api.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk.Web"></Project>\n')
    (root / "src/Shop.Api/Infra/TodoReadRepository.cs").write_text(THIS_BASE)
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="shop", ref="main", commit_sha="x", root=str(root)), convs=[])
    sym = {s.id: s.name for s in res.symbols}
    assert {(c.callee_name, c.receiver) for c in res.calls} >= {("Exists", "this"), ("FindByIdAsync", "base")}
    assert [(sym[e.caller_id], sym[e.callee_id], e.strategy) for e in rv.calls] == [("NotExists", "Exists", "receiver-type")]


def test_base_call_without_base_list_is_not_a_self_edge(tmp_path: Path):
    """`partial class View` (base declared in XAML) or implicit `object`: `base.X()` has no type at all."""
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    root = tmp_path / "app"
    root.mkdir()
    (root / "View.cs").write_text("namespace App;\n\npublic partial class View\n{\n"
                                  "    protected override void OnAppearing() { base.OnAppearing(); }\n}\n")
    with contextlib.redirect_stderr(io.StringIO()):
        _, rv = extract_and_resolve(RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root)), convs=[])
    assert rv.calls == []


def test_package_base_methods_keep_the_dependency_on_the_type(tmp_path):
    """`repo.CreateAsync()` on `ITodoRepository : IBaseRepository<T>` (a package): CALLS to the interface and its
    single implementer with the method name (`inherited` / `inherited-impl`). An overloaded method of the
    repo is not inherited (the argument count picks the overload; the same arity links all of them,
    ambiguous), and a type without outside bases gets no edge."""
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    files = {
        "src/App/App.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>\n',
        "src/App/ITodoRepository.cs": "namespace App;\n\npublic interface ITodoRepository : IBaseRepository<Todo, Guid> { }\n",
        "src/App/TodoRepository.cs": "namespace App;\n\npublic class TodoRepository : BaseRepository<Todo, Guid>, ITodoRepository { }\n",
        "src/App/Todo.cs": ("namespace App;\n\npublic class Todo : BaseModel\n{\n"
                            "    public static Todo Create(string name) => new();\n"
                            "    public static Todo Create(Guid id, string name, params string[] tags) => new();\n"
                            "    public static Todo Mark(int n) => new();\n"
                            "    public static Todo Mark(long n) => new();\n}\n"),
        "src/App/Plain.cs": "namespace App;\n\npublic class Plain { }\n",
        "src/App/Handler.cs": ("namespace App;\n\npublic class Handler(ITodoRepository repo, Plain plain)\n{\n"
                               "    public async Task Handle(string name)\n    {\n"
                               "        var todo = Todo.Create(name);\n"
                               "        Todo.Create(Guid.Empty, name, \"a\", \"b\");\n"
                               "        Todo.Mark(1);\n"
                               "        await repo.CreateAsync(todo);\n"
                               "        plain.Missing();\n    }\n}\n"),
    }
    root = tmp_path / "app"
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    repo = RepoInfo(tenant="t", name="app", ref="main", commit_sha="x", root=str(root))
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(repo)
    sym = {s.id: s for s in res.symbols}
    def line(x):                       # the overload, by the line it is declared on
        return x.line_start if x.kind == "method" else None
    got = {(sym[e.callee_id].qualified_name, line(sym[e.callee_id]), e.line, e.strategy, e.method)
           for e in rv.calls if sym.get(e.caller_id) and sym[e.caller_id].name == "Handle"}
    assert got == {
        ("App.Todo.Create", 5, 7, "receiver-type", None),                  # Create(name): 1 argument
        ("App.Todo.Create", 6, 8, "receiver-type", None),                  # Create(id, name, params tags): 4 arguments
        ("App.Todo.Mark", 7, 9, "receiver-type-ambiguous", None),          # Mark(int) / Mark(long): same arity
        ("App.Todo.Mark", 8, 9, "receiver-type-ambiguous", None),
        ("App.ITodoRepository", None, 10, "inherited", "CreateAsync"),
        ("App.TodoRepository", None, 10, "inherited-impl", "CreateAsync"),
    }
