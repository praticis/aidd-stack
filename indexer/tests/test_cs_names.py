"""What a name means in C#, asked by the resolver for a call's receiver and by the HTTP scanner for the client wrapper
a call goes through. A type's simple name is looked up as C# looks it up: in the namespace the code is in, then in each
one around it out to the global namespace, each followed by the `using`s its declaration holds; the file's own `using`s
come last, with every `global using` of its project. Of the global namespace, only the file's own project counts: other
projects keep their programs there.

A capitalized name the caller's type has as a member, declared on it, on another of its parts or on a base of the repo,
is that member, not a type of its name, and so is a type nested in one of them. With a base outside the repo, which may
declare the member, the name is still read as the type's, and a member after it is a value, which an extension may take.
A type nested in another is no name of its namespace: only the file that declares it, or the types deriving from the one
it is in, see it by its simple name, and a type nested in another is named with it on both sides. A call with no
receiver is a method of the caller's own type, never a client's, unless it is given the request's verb: then it is a
request the type, or a base of it, sends.

A member, a parameter or a local whose type is a type parameter has the type its one constraint names; with none, or
more than one, it declares none, and its call goes by name. A member whose type is a type parameter of the type that
declares it has, before that, the type argument given for it: by the type a local or a parameter writes
(`Holder<HttpService> h`), or by the base lists down from the caller's type (`: Generic<HttpService>`)."""

import contextlib
import io

import pytest

SERVICES = """namespace Api.Services;

public static class Urls { public const string Base = "https://api.example.test/"; }

public interface IHttpService { Task<T?> HttpGet<T>(string uri); }

public class HttpService : IHttpService
{
    private readonly HttpClient _httpClient;
    private readonly string _apiUrl;
    public HttpService(HttpClient httpClient, string apiBase) { _httpClient = httpClient; _apiUrl = apiBase; }
    public Task<T?> HttpGet<T>(string uri) => _httpClient.GetFromJsonAsync<T>($"{_apiUrl}{uri}");
    public void Ping() { }
}

public static class Engine
{
    public static HttpService Current { get; } = new HttpService(new HttpClient(), Urls.Base);
}

public abstract class Generic<TService> { protected TService Http { get; } }

public abstract class Middle<T> : Generic<T> { }

public class Holder<T> { public T Value { get; } }

public abstract class BaseController
{
    protected static class Error { public static Task BadRequest() => Task.CompletedTask; }
}

public static class HttpExtensions { public static Task Warm(this IHttpService s) => Task.CompletedTask; }

public class Http
{
    public Task<T?> HttpGet<T>(string uri) => Task.FromResult(default(T));
    public static Task Reset() => Task.CompletedTask;
}

public abstract class Feature { public HttpService Http { get; } = new HttpService(new HttpClient(), Urls.Base); }

public abstract class DeepFeature : Feature { }

public abstract class LoggedFeature { public ILogger Http { get; } }

public class Disk
{
    public Task<string> Read(string subpath) => GetAsync(subpath, p => p);
    private Task<string> GetAsync(string path, Func<string, string> read) => Task.FromResult(read(path));
}

public abstract class Relay
{
    protected Task SendAsync<TRequest>(HttpMethod method, string path, TRequest body) => Task.CompletedTask;
}
"""
LEDGER = "namespace Api;\n\npublic class Ledger { public void Post() { } }\n"
LEGACY = """namespace Api.Legacy
{
    public class HttpService { public Task<T?> HttpGet<T>(string uri) => Task.FromResult(default(T)); }
    public class Ledger { public void Post() { } }
    public class Clock { public void Tick() { } }
    public class Error { public static Task BadRequest() => Task.CompletedTask; }
}
"""
CLIENT = """%(usings)s
%(namespace)s
%(inner)s
public %(partial)sclass ItemsClient%(declaration)s
{
%(members)s
    public async Task Run(%(params)s)
    {
%(body)s
    }
}
%(close)s
"""
OTHER_PART = """using Api.Services;

namespace Api.Items;

public partial class ItemsClient { public HttpService Http { get; } = new HttpService(new HttpClient(), Urls.Base); }
"""
NESTED = "namespace Api.Items;\n\npublic class Box { public class Ledger { public void Post() { } } }\n"
TOOLS = {"Tools/Tools.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>',
         "Tools/Ledger.cs": "public class Ledger { public void Post() { } }\n"}
GLOBAL_USING = "global using Api.Services;\n"
GET = 'await svc.HttpGet<string>("items");'
BOUND = "<TService> where TService : HttpService"
NO_ARGUMENT = "by name: the type argument a base list passes is not read"
HTTP_GET = 'await Http.HttpGet<string>("items");'
TYPED = {("Api.Services.HttpService.HttpGet", "receiver-type")}
WRAPPED = {("GET", "/items")}


def block(ns: str) -> dict:
    return {"namespace": f"namespace {ns}\n{{", "close": "}"}


def case(id, edges, calls=frozenset(), resolver=None, scanner=None, **fields):
    """`resolver` / `scanner`: what that side gives today when it is wrong, an xfail on that side. `every`: the edges
    found by name count too."""
    return id, fields, edges, set(calls), resolver, scanner


def _params(side: int):
    """One side's expectation per case, an xfail where that side is wrong today."""
    out = []
    for id, fields, edges, calls, *wrong in CASES:
        marks = pytest.mark.xfail(strict=True, reason=wrong[side]) if wrong[side] else ()
        out.append(pytest.param(fields, (edges, calls)[side], id=id, marks=marks))
    return out


CASES = [
    case("a-type-of-the-block-namespace-before-a-using", TYPED, WRAPPED, usings="using Api.Legacy;",
         params="HttpService svc", body=GET, **block("Api.Services")),
    case("a-type-of-the-block-namespace", TYPED, WRAPPED, usings="", params="HttpService svc", body=GET,
         **block("Api.Services")),
    case("a-type-of-the-file-namespace-before-a-using", TYPED, WRAPPED, usings="using Api.Legacy;",
         namespace="namespace Api.Services;", params="HttpService svc", body=GET),
    case("a-type-of-an-enclosing-namespace-before-a-using", {("Api.Ledger.Post", "receiver-type")},
         usings="using Api.Legacy;", params="Ledger l", body="l.Post();"),
    case("a-type-of-the-global-namespace-before-a-using", {("Clock.Tick", "receiver-type")},
         usings="using Api.Legacy;", params="Clock c", body="c.Tick();"),
    case("a-using-of-the-block-before-an-enclosing-namespace", {("Api.Legacy.Ledger.Post", "receiver-type")},
         inner="using Api.Legacy;", params="Ledger l", body="l.Post();", **block("Api.Items")),
    case("a-type-a-using-shows", {("Api.Legacy.Ledger.Post", "receiver-type")}, usings="using Api.Legacy;",
         namespace="namespace Shop.Items;", params="Ledger l", body="l.Post();"),
    case("a-type-of-the-global-namespace-of-another-project", {("Api.Legacy.Ledger.Post", "receiver-type")},
         usings="using Api.Legacy;", namespace="namespace Shop.Items;", params="Ledger l", body="l.Post();",
         files=TOOLS),
    case("a-type-a-global-using-of-the-project-shows", TYPED, WRAPPED,
         usings="", params="HttpService svc", body=GET, files={"Usings.cs": GLOBAL_USING}),
    case("a-global-using-of-another-project-is-not-seen", set(), WRAPPED, usings="", params="HttpService svc",
         body=GET, files={"Tools/Tools.csproj": TOOLS["Tools/Tools.csproj"], "Tools/Usings.cs": GLOBAL_USING}),
    case("a-type-nested-in-another-is-no-name-of-its-namespace", {("Api.Ledger.Post", "receiver-type")},
         params="Ledger l", body="l.Post();", files={"Items/Box.cs": NESTED}),
    case("a-type-nested-in-the-callers", {("Api.Items.ItemsClient.Ledger.Post", "receiver-type")},
         params="Ledger l", body="l.Post();", members="    public class Ledger { public void Post() { } }"),
    case("a-member-a-base-of-the-repo-declares", TYPED, WRAPPED, declaration=" : Feature", body=HTTP_GET),
    case("a-member-a-base-two-levels-up-declares", TYPED, WRAPPED, declaration=" : DeepFeature", body=HTTP_GET),
    case("an-extension-of-the-members-type", {("Api.Services.HttpExtensions.Warm", "receiver-type")},
         declaration=" : Feature", body="await Http.Warm();"),
    case("a-member-another-part-of-the-type-declares", TYPED, WRAPPED, partial="partial ", body=HTTP_GET,
         files={"Items/ItemsClient.Http.cs": OTHER_PART}),
    case("the-types-own-member", TYPED, WRAPPED, body=HTTP_GET,
         members="    public HttpService Http { get; } = new HttpService(new HttpClient(), Urls.Base);"),
    case("a-static-call-on-the-type", {("Api.Services.Http.Reset", "receiver-type")}, body="await Http.Reset();"),
    case("a-call-on-the-types-name-reaches-no-extension", set(), body="await Http.Warm();"),
    case("a-member-whose-type-is-outside-the-repo", set(), declaration=" : LoggedFeature", body=HTTP_GET),
    case("a-name-a-base-outside-the-repo-may-declare", {("Api.Services.Http.Reset", "receiver-type")},
         declaration=" : ControllerBase", body="await Http.Reset();"),
    case("an-extension-of-a-member-after-a-types-name", {("Api.Services.HttpExtensions.Warm", "receiver-type")},
         body="await Engine.Current.Warm();"),
    case("a-member-whose-type-is-a-type-parameter-goes-by-name", {("Api.Services.HttpService.Ping", "same-module")},
         declaration="<TService> : Generic<TService>", body="Http.Ping();", every=True),
    case("a-member-typed-by-a-type-parameter-a-base-list-passes", TYPED, WRAPPED,
         resolver=NO_ARGUMENT, scanner="none: the member declares no type", declaration=" : Generic<HttpService>",
         body=HTTP_GET),
    case("a-type-argument-passed-on-through-two-base-lists", TYPED, WRAPPED,
         resolver=NO_ARGUMENT, scanner="none: the member declares no type", declaration=" : Middle<HttpService>",
         body=HTTP_GET),
    case("a-type-parameter-the-caller-constrains-passed-to-its-base", TYPED, WRAPPED,
         resolver=NO_ARGUMENT, scanner="none: the member declares no type",
         declaration="<TService> : Generic<TService> where TService : HttpService", body=HTTP_GET),
    case("a-member-typed-by-a-type-parameter-of-a-parameters-type", TYPED, WRAPPED,
         resolver="none: the type arguments the parameter's type writes are not read",
         scanner="none: the member declares no type", params="Holder<HttpService> h",
         body='await h.Value.HttpGet<string>("items");'),
    case("a-member-typed-by-a-type-parameter-of-a-locals-type", TYPED, WRAPPED,
         resolver="none: the type arguments the local's type writes are not read",
         scanner="none: the member declares no type",
         body='var h = new Holder<HttpService>();\nawait h.Value.HttpGet<string>("items");'),
    case("a-member-whose-type-is-a-constrained-type-parameter", TYPED, WRAPPED, declaration=BOUND, body=HTTP_GET,
         members="    protected TService Http { get; }"),
    case("a-parameter-whose-type-is-a-constrained-type-parameter", TYPED, WRAPPED, declaration=BOUND,
         params="TService svc", body=GET),
    case("a-parameter-of-a-local-functions-constrained-type-parameter", TYPED, WRAPPED,
         body='async Task Go<T>(T s) where T : HttpService { await s.HttpGet<string>("items"); }'),
    case("a-value-of-a-type-parameter-with-two-constraints-goes-by-name",
         {("Api.Services.HttpService.Ping", "same-module")},
         declaration="<TService> where TService : IHttpService, IDisposable", params="TService svc",
         body="svc.Ping();", every=True),
    case("a-member-of-a-caller-nested-in-another-type", TYPED, WRAPPED,
         inner="public class Outer\n{", close="}",
         members="    private readonly HttpService svc = new HttpService(new HttpClient(), Urls.Base);", body=GET),
    case("a-type-nested-in-a-base-of-the-callers", {("Api.Services.BaseController.Error.BadRequest", "receiver-type")},
         usings="using Api.Services;\nusing Api.Legacy;", declaration=" : BaseController",
         body="await Error.BadRequest();"),
    case("a-call-with-no-receiver-is-the-types-own-method", {("Api.Services.Disk.Read", "receiver-type")},
         params="Disk d", body='await d.Read("images/flags");'),
    case("a-call-with-no-receiver-given-the-verb-is-a-request", {("Api.Services.Relay.SendAsync", "same-module")},
         {("POST", "/push/register")},
         declaration=" : Relay", body='await SendAsync(HttpMethod.Post, "push/register", new object());', every=True),
]


def _extract(root, fields: dict):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    body = "\n".join(" " * 8 + line for line in fields.get("body", "").splitlines())
    client = CLIENT % ({"usings": "using Api.Services;", "namespace": "namespace Api.Items;", "inner": "",
                        "partial": "", "declaration": "", "members": "", "params": "", "close": ""}
                       | {k: v for k, v in fields.items() if k != "files"} | {"body": body})
    files = {"Api.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>', "Services/HttpService.cs": SERVICES,
             "Legacy/Legacy.cs": LEGACY, "Ledger.cs": LEDGER,
             "Clock.cs": "public class Clock { public void Tick() { } }\n", "Items/ItemsClient.cs": client,
             **fields.get("files", {})}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)))


@pytest.mark.parametrize("fields,expected", _params(0))
def test_a_name_reaches_what_csharp_means_by_it(tmp_path, fields, expected):
    res, rv = _extract(tmp_path, fields)
    names = {s.id: s.qualified_name for s in res.symbols}
    found = {(names[c.callee_id], c.strategy) for c in rv.calls
             if names.get(c.caller_id, "").endswith(".ItemsClient.Run")
             and (fields.get("every") or c.strategy.startswith(("receiver-type", "inherited")))}
    assert found == expected


@pytest.mark.parametrize("fields,expected", _params(1))
def test_a_call_goes_through_the_wrapper_csharp_means(tmp_path, fields, expected):
    res, _ = _extract(tmp_path, fields)
    assert {(c.method, c.path) for c in res.http_calls if "ItemsClient" in c.evidence} == expected
