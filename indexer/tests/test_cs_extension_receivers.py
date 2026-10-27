"""Which extension method a C# call reaches when only one can serve it: the type its receiver's chain ends in is outside
the repo, or the receiver's type is unknown and the call passes type arguments. C# proves an extension cannot take
the call when the call passes type arguments it declares no type parameters for, or when its `this` is a type of the
repo and the receiver's type is outside the repo, which no type of the repo can be. A `this` is a type of the repo only
when C#'s scopes reach one from the extension's file with as many type parameters as the `this` passes type arguments:
a type of the repo that shares its name with a framework's is not it. A type outside the repo met before the chain's
end (`_lazy.Value`) says nothing of what the receiver is, and proves nothing.

Dropping the extensions that cannot take the call may only take targets away. One whose `this` may or may not take the
receiver keeps the strategy it had beside them, `-ambiguous` included. One whose `this` is the receiver's type, or takes
any value, takes the strategy left, and is a new target only when it is the only one. A `this` of a predefined type
(`this string`) has no name in the type facts, so it is never known to take a value: dropping its overloads adds no
target."""

import contextlib
import io

import pytest

SERVICES = """namespace Api.Services;

public interface ISender { }
public interface IStore { }
public interface IThing { }
public interface ICollection { }
public class Message { }

public static class Sending { public static Task SendAsync(this ISender s, Message m) => Task.CompletedTask; }
public static class Dates { public static DateTime EnsureUtc(this DateTime d) => d; }
public static class Sets { public static object Freeze<T>(this ISet<T> s) => s; }
public static class Heads { public static T? Head<T>(this ICollection<T> c) => default; }
public static class StoreListing { public static object Snapshot(this IStore s) => s; }
public static class Listing { public static IReadOnlyList<T> Snapshot<T>(this IEnumerable<T> s) => null!; }
public static class TextPicks { public static object Pick(this IThing t, string s) => t; }
public static class NumberPicks { public static object Pick(this IThing t, int n) => t; }
public static class Picks { public static T? Pick<T>(this IThing t, string s) => default; }
public static class AnyPicks { public static T? Pick<T>(this T t, string s, int n = 0) => default; }
"""
CACHING = "namespace Api.Caching;\n\npublic interface ISet<T> { }\n"
LIB = """namespace Lib;

public interface IBag { }

public static class Bags
{
    public static T? Get<T>(this IBag b, string key) => default;
    public static object? Get(this IBag b, string key) => null;
}

public static class Queries
{
    extension(IQueryable query)
    {
        public T Context<T>() => default!;
        public object Context() => null!;
    }
}

public static class Converter
{
    public static T? TryConvertTo<T>(this object? value, object? options = null) => default;
    public static object? TryConvertTo(this object? value, Type type, object? options = null) => null;
}

public static class Hashing
{
    public static string Digest<T>(this string s) => s;
    public static string Digest(this string s) => s;
}
"""
LOCAL = """public static class LocalStoreListing { public static object Peek(this IStore s) => s; }
public static class LocalListing { public static IReadOnlyList<T> Peek<T>(this IEnumerable<T> s) => null!; }
"""
CLIENT = """using Api.Services;
using Lib;

namespace Api.Items;

%(inner)s
public class ItemsClient
{
%(members)s
    public async Task Run(%(params)s)
    {
        %(body)s
    }
}
"""


def case(id, edges, **fields):
    return pytest.param(fields, edges, id=id)


CASES = [
    case("an-outside-receiver-reaches-no-extension-of-a-repo-type", set(),
         params="HttpClient http, Message m", body="await http.SendAsync(m);"),
    case("an-outside-type-before-the-chain-end-proves-nothing", {("Api.Services.Sending.SendAsync", "same-module")},
         members="    private readonly Lazy<ISender> _sender = new(() => null!);", params="Message m",
         body="await _sender.Value.SendAsync(m);"),
    case("a-parameter-before-the-chain-end-is-an-unknown-receiver", {("Api.Services.Sending.SendAsync", "same-module")},
         params="Lazy<ISender> sender, Message m", body="await sender.Value.SendAsync(m);"),
    case("a-nullable-value-keeps-the-extension-of-its-type", {("Api.Services.Dates.EnsureUtc", "same-module")},
         members="    private readonly DateTime? _at = null;", body="_at.Value.EnsureUtc();"),
    case("a-repo-type-the-extension-file-does-not-see-proves-nothing", {("Api.Services.Sets.Freeze", "same-module")},
         params="HashSet<string> tags", body="tags.Freeze();"),
    case("a-repo-type-of-another-arity-proves-nothing", {("Api.Services.Heads.Head", "same-module")},
         params="List<string> items", body="items.Head();"),
    case("dropping-an-overload-makes-no-unique-name", set(),
         body='Func<object, string?> f = x => x.Get<string>("key");'),
    case("dropping-a-rival-in-the-module-keeps-the-guess-ambiguous",
         {("Api.Services.Listing.Snapshot", "same-module-ambiguous")}, params="IList<string> items",
         body="items.Snapshot();"),
    case("dropping-a-rival-in-the-file-keeps-the-guess-ambiguous",
         {("Api.Items.LocalListing.Peek", "same-file-ambiguous")}, inner=LOCAL, params="IList<string> items",
         body="items.Peek();"),
    case("dropping-an-overload-leaves-the-extension-of-the-receivers-type",
         {("Lib.Queries.Context", "unique-name")},
         params="IQueryable<Message> query", body="query.Context<Message>();"),
    case("dropping-an-overload-leaves-the-extension-of-any-value", {("Lib.Converter.TryConvertTo", "unique-name")},
         body="Func<object, int?> f = x => x.TryConvertTo<int>(null);"),
    case("a-target-of-any-value-the-dropping-lets-in-is-no-new-guess",
         {("Api.Services.Picks.Pick", "same-module-ambiguous")},
         body='Func<object, string?> f = x => x.Pick<string>("text");'),
    case("an-extension-of-a-predefined-type-is-never-known-to-take-a-value", set(),
         params="string url", body="url.Digest<object>();"),
]


def _calls(root, fields: dict) -> set[tuple[str, str]]:
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    client = CLIENT % ({"inner": "", "members": "", "params": ""} | fields)
    files = {"Api.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>', "Services/Services.cs": SERVICES,
             "Caching/Set.cs": CACHING, "Lib/Lib.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>',
             "Lib/Lib.cs": LIB, "Items/ItemsClient.cs": client}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)))
    names = {s.id: s.qualified_name for s in res.symbols}
    return {(names[c.callee_id], c.strategy) for c in rv.calls
            if names.get(c.caller_id, "").endswith(".ItemsClient.Run")}


@pytest.mark.parametrize("fields,expected", CASES)
def test_an_extension_takes_the_receiver_csharp_proves_it_can(tmp_path, fields, expected):
    assert _calls(tmp_path, fields) == expected
