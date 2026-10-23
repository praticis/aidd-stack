"""What a name means in C#, asked by the resolver for a call's receiver and by the HTTP scanner for the client wrapper
a call goes through. A type's simple name is looked up as C# looks it up: in the namespace the code is in, then in each
one around it out to the global namespace, each followed by the `using`s its declaration holds; the file's own `using`s
come last. A capitalized name the caller's type has as a member, declared on it, on another of its parts or on a base
of the repo, is that member, not a type of its name. With a base outside the repo, which may declare the member, the
name is still read as the type's."""

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
"""
LEGACY = """namespace Api.Legacy
{
    public class HttpService { public Task<T?> HttpGet<T>(string uri) => Task.FromResult(default(T)); }
    public class Ledger { public void Post() { } }
    public class Clock { public void Tick() { } }
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
GET = 'await svc.HttpGet<string>("items");'
HTTP_GET = 'await Http.HttpGet<string>("items");'
TYPED = {("Api.Services.HttpService.HttpGet", "receiver-type")}
WRAPPED = {("GET", "/items")}
USING = "the using's homonym: the block namespace is not seen"
HOMONYM = "the homonym type `Http`: a member the type inherits is read as a static access to a type"
NOT_A_WRAPPER = "none: read as the type `Http`, which wraps no client"


def block(ns: str) -> dict:
    return {"namespace": f"namespace {ns}\n{{", "close": "}"}


def case(id, edges, calls=frozenset(), resolver=None, scanner=None, **fields):
    """`resolver` / `scanner`: what that side gives today when it is wrong, an xfail on that side."""
    return id, fields, edges, set(calls), resolver, scanner


CASES = [
    case("a-type-of-the-block-namespace-before-a-using", TYPED, WRAPPED, resolver=USING, usings="using Api.Legacy;",
         params="HttpService svc", body=GET, **block("Api.Services")),
    case("a-type-of-the-block-namespace", TYPED, WRAPPED, resolver="none: the block namespace is not seen", usings="",
         params="HttpService svc", body=GET, **block("Api.Services")),
    case("a-type-of-the-file-namespace-before-a-using", TYPED, WRAPPED,
         resolver="none: the file's namespace and the using's count alike", usings="using Api.Legacy;",
         namespace="namespace Api.Services;", params="HttpService svc", body=GET),
    case("a-type-of-an-enclosing-namespace-before-a-using", {("Api.Ledger.Post", "receiver-type")},
         resolver="the using's homonym: the namespaces around the file's are not seen", usings="using Api.Legacy;",
         params="Ledger l", body="l.Post();"),
    case("a-type-of-the-global-namespace-before-a-using", {("Clock.Tick", "receiver-type")},
         resolver="the using's homonym: the global namespace is not seen", usings="using Api.Legacy;",
         params="Clock c", body="c.Tick();"),
    case("a-using-of-the-block-before-an-enclosing-namespace", {("Api.Legacy.Ledger.Post", "receiver-type")},
         inner="using Api.Legacy;", params="Ledger l", body="l.Post();", **block("Api.Items")),
    case("a-type-a-using-shows", {("Api.Legacy.Ledger.Post", "receiver-type")}, usings="using Api.Legacy;",
         namespace="namespace Shop.Items;", params="Ledger l", body="l.Post();"),
    case("a-member-a-base-of-the-repo-declares", TYPED, WRAPPED, resolver=HOMONYM, scanner=NOT_A_WRAPPER,
         declaration=" : Feature", body=HTTP_GET),
    case("a-member-a-base-two-levels-up-declares", TYPED, WRAPPED, resolver=HOMONYM, scanner=NOT_A_WRAPPER,
         declaration=" : DeepFeature", body=HTTP_GET),
    case("an-extension-of-the-members-type", {("Api.Services.HttpExtensions.Warm", "receiver-type")},
         resolver="none: read as the type `Http`, whose name reaches no extension", declaration=" : Feature",
         body="await Http.Warm();"),
    case("a-member-another-part-of-the-type-declares", TYPED, WRAPPED, resolver=HOMONYM, scanner=NOT_A_WRAPPER,
         partial="partial ", body=HTTP_GET, files={"Items/ItemsClient.Http.cs": OTHER_PART}),
    case("the-types-own-member", TYPED, WRAPPED, body=HTTP_GET,
         members="    public HttpService Http { get; } = new HttpService(new HttpClient(), Urls.Base);"),
    case("a-static-call-on-the-type", {("Api.Services.Http.Reset", "receiver-type")}, body="await Http.Reset();"),
    case("a-call-on-the-types-name-reaches-no-extension", set(), body="await Http.Warm();"),
    case("a-member-whose-type-is-outside-the-repo", set(), resolver=HOMONYM, declaration=" : LoggedFeature",
         body=HTTP_GET),
    case("a-name-a-base-outside-the-repo-may-declare", {("Api.Services.Http.Reset", "receiver-type")},
         declaration=" : ControllerBase", body="await Http.Reset();"),
]


def _params(side: int):
    """One side's expectation per case, an xfail where that side is wrong today."""
    out = []
    for id, fields, edges, calls, *wrong in CASES:
        marks = pytest.mark.xfail(strict=True, reason=wrong[side]) if wrong[side] else ()
        out.append(pytest.param(fields, (edges, calls)[side], id=id, marks=marks))
    return out


def _extract(root, fields: dict):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    body = "\n".join(" " * 8 + line for line in fields.get("body", "").splitlines())
    client = CLIENT % ({"usings": "using Api.Services;", "namespace": "namespace Api.Items;", "inner": "", "partial": "",
                        "declaration": "", "members": "", "params": "", "close": ""}
                       | {k: v for k, v in fields.items() if k != "files"} | {"body": body})
    files = {"Api.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>', "Services/HttpService.cs": SERVICES,
             "Legacy/Legacy.cs": LEGACY, "Ledger.cs": "namespace Api;\n\npublic class Ledger { public void Post() { } }\n",
             "Clock.cs": "public class Clock { public void Tick() { } }\n", "Items/ItemsClient.cs": client,
             **fields.get("files", {})}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)))


@pytest.mark.parametrize("fields,edges", _params(0))
def test_a_name_reaches_what_csharp_means_by_it(tmp_path, fields, edges):
    res, rv = _extract(tmp_path, fields)
    names = {s.id: s.qualified_name for s in res.symbols}
    found = {(names[c.callee_id], c.strategy) for c in rv.calls if names.get(c.caller_id, "").endswith(".ItemsClient.Run")
             and c.strategy.startswith(("receiver-type", "inherited"))}
    assert found == edges


@pytest.mark.parametrize("fields,calls", _params(1))
def test_a_call_goes_through_the_wrapper_csharp_means(tmp_path, fields, calls):
    res, _ = _extract(tmp_path, fields)
    assert {(c.method, c.path) for c in res.http_calls if "ItemsClient" in c.evidence} == calls
