"""A call on a receiver whose type the code declares, when no method of the type takes its arguments: C# goes on to
the extension methods in scope, so the call reaches the repo's extension whose `this` takes the type, a base of it or
an interface it names, the nearest first. Failing that, the only one that takes any value; on a type with a base
outside the repo, only when no other method of the repo has its name, since that base may declare the method. One that
takes another type, an array or a predefined type is not its target, and a call on the type's name has no value to
take. A package's type written with its namespace is the type of its last name."""

import contextlib
import io

import pytest

SERVICES = """namespace Api.Services;

public interface IStore { string Name(); }

public class Store : IStore
{
    public string Name() => "store";
    public int Count(int a) => a;
    public int Count(string a) => 0;
    public string Load() => "";
}

public class ChildStore : Store { }

public class Other { }

public class Db : DbContext { }

public static class StoreExtensions
{
    public static string Ping(this Store s) => s.Name();
    public static string Warm(this IStore s) => s.Name();
    public static string Near(this IStore s) => s.Name();
    public static string Near(this Store s) => s.Name();
    public static int Count(this Store s, int a, int b) => a + b;
    public static string Load(this Store s) => "";
    public static void Seed(this DbContext db) { }
    public static void Clean(this Other o) { }
    public static int Total(this Store[] all) => all.Length;
    public static bool Blank(this string s) => s == "";
}

public static class AnyExtensions
{
    public static T Tap<T>(this T value) => value;
    public static string Dump(this object value) => "";
    public static T Twice<T>(this T value) => value;
}

public static class MoreExtensions
{
    public static T Twice<T>(this T value) => value;
    public static T Name<T>(this T value) => value;
}

public static class PackageExtensions
{
    public static IQueryable<T> Where<T>(this Microsoft.EntityFrameworkCore.DbSet<T> set, Func<T, bool> p) => null;
    public static int Size(this IDisposable d) => 0;
}
"""
HOMONYM = """namespace Api.Legacy;

public class Store { }

public static class LegacyExtensions
{
    public static void Shine(this Store s) { }
}
"""
CLIENT = """using Api.Services;

namespace Api.Items;

public class ItemsClient
{
    public void Run(%(params)s)
    {
        %(body)s
    }
}
"""


def case(id, params, body, edges):
    return pytest.param(params, body, edges, id=id)


CASES = [
    case("an-extension-of-the-type", "Store store", "store.Ping();",
         {("StoreExtensions.Ping", "receiver-type")}),
    case("an-extension-of-a-base", "ChildStore store", "store.Ping();",
         {("StoreExtensions.Ping", "receiver-type")}),
    case("an-extension-of-an-interface-it-implements", "Store store", "store.Warm();",
         {("StoreExtensions.Warm", "receiver-type")}),
    case("an-extension-of-the-interface", "IStore store", "store.Warm();",
         {("StoreExtensions.Warm", "receiver-type")}),
    case("the-extension-of-the-nearest-type", "Store store", "store.Near();",
         {("StoreExtensions.Near", "receiver-type")}),
    case("an-extension-when-no-overload-takes-the-arguments", "Store store", "store.Count(1, 2);",
         {("StoreExtensions.Count", "receiver-type")}),
    case("an-extension-of-a-base-outside-the-repo", "Db db", "db.Seed();",
         {("StoreExtensions.Seed", "receiver-type")}),
    case("the-only-extension-of-any-value", "Store store", "store.Tap();",
         {("AnyExtensions.Tap", "unique-name")}),
    case("the-only-extension-of-object", "Store store", "store.Dump();",
         {("AnyExtensions.Dump", "unique-name")}),
    case("the-types-own-method-wins", "ChildStore store", "store.Load();", {("Store.Load", "receiver-type")}),
    case("an-extension-of-another-type", "Store store", "store.Clean();", set()),
    case("an-extension-of-an-array", "Store store", "store.Total();", set()),
    case("an-extension-of-a-predefined-type", "Store store", "store.Blank();", set()),
    case("an-extension-of-a-homonym-type", "Store store", "store.Shine();", set()),
    case("two-extensions-of-any-value", "Store store", "store.Twice();", set()),
    case("the-only-method-of-its-name-on-a-type-with-a-base-outside-the-repo", "Db db", "db.Tap();",
         {("AnyExtensions.Tap", "unique-name")}),
    case("an-extension-of-a-type-outside-the-repo-its-base-may-be", "Db db", "db.Size();", {("Db", "inherited")}),
    case("a-call-on-the-types-name", "", "Store.Ping();", set()),
    case("a-name-another-method-of-the-repo-has-on-a-type-with-a-base-outside-the-repo", "Db db", "db.Name();",
         {("Db", "inherited")}),
    case("an-extension-of-a-type-outside-the-repo-on-a-type-with-no-base-outside", "Store store", "store.Size();",
         set()),
    case("an-extension-of-a-package-type-written-with-its-namespace", "DbSet<Store> stores", "stores.Where(s => true);",
         {("PackageExtensions.Where", "same-module")}),
]


def _edges(root, params: str, body: str) -> set[tuple[str, str]]:
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    files = {"Api.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>', "Services/Store.cs": SERVICES,
             "Legacy/Store.cs": HOMONYM, "Items/ItemsClient.cs": CLIENT % {"params": params, "body": body}}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)))
    names = {s.id: s.qualified_name.removeprefix("Api.Services.") for s in res.symbols}
    return {(names[c.callee_id], c.strategy) for c in rv.calls if names.get(c.caller_id) == "Api.Items.ItemsClient.Run"}


@pytest.mark.parametrize("params,body,edges", CASES)
def test_a_call_the_type_does_not_take_reaches_the_extension_that_takes_it(tmp_path, params, body, edges):
    assert _edges(tmp_path, params, body) == edges
