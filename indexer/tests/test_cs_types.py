"""C#'s one answer to "what type does the code declare for this value", which the resolver asks to type call
receivers for `CALLS` and the HTTP scanner to find the client wrapper a call goes through. The two sides once had
answers of their own, and each case here is one they gave differently. A guard passes on both sides; an xfail is
strict, so it fails the suite once it passes."""

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

public class Other { public Task<T?> HttpGet<T>(string uri) => Task.FromResult(default(T)); }

public class Holder { public HttpService Svc { get; } = new HttpService(new HttpClient(), Urls.Base); }

public class BaseClient { protected HttpService _base = new HttpService(new HttpClient(), Urls.Base); }
"""
CLIENT = """using Api.Services;
%(usings)s
namespace Api.Items;

public class Item {}

public class ItemsClient%(declaration)s
{
%(members)s
    public async Task Run(%(params)s)
    {
%(body)s
    }
%(more)s
}
"""
NEW = "new HttpService(new HttpClient(), Urls.Base)"
GET = 'await svc.HttpGet<Item>("items");'
FIELD = f"    private readonly HttpService svc = {NEW};"
OTHER_FIELD = "    private readonly Other svc = new Other();"
MAKE = f"    HttpService Make() => {NEW};"
# another type of the same simple name, which the client's file sees through a `using`
HOMONYM = {"Other/ItemsClient.cs": "namespace Api.Other;\n\npublic class ItemsClient { public object svc; }\n"}

TYPED = {("HttpService.HttpGet", "receiver-type")}
THROUGH_THE_WRAPPER = {("GET", "/items")}
THROUGH_THE_INTERFACE = {("IHttpService.HttpGet", "receiver-type"), ("HttpService.HttpGet", "receiver-type-impl")}


def case(id, resolver=None, scanner=None, edges=TYPED, calls=THROUGH_THE_WRAPPER, **fields):
    """`resolver` / `scanner`: what that side gives today when it is wrong, an xfail on that side. A name whose
    declaration states no type is typed by nothing, so neither side reaches a method or a wrapper through it."""
    return id, fields, (edges, calls), resolver, scanner


CASES = [
    case("a-parameter", params="HttpService svc", body=GET),
    case("a-local-created-with-new", body=f"var svc = {NEW};\n{GET}"),
    case("a-local-of-a-written-type", body=f"HttpService svc = Make();\n{GET}", more=MAKE),
    case("a-field", members=FIELD, body=GET),
    case("a-property", members="    public HttpService svc { get; set; }", body=GET),
    case("a-primary-constructor-parameter", declaration="(HttpService svc)", body=GET),
    case("an-interface-typed-field", members="    private readonly IHttpService svc;", body=GET,
         edges=THROUGH_THE_INTERFACE),
    case("a-service-the-container-builds", params="IServiceProvider sp",
         body=f"var svc = sp.GetRequiredService<HttpService>();\n{GET}"),
    case("the-result-of-an-own-method", body=f"var svc = Make();\n{GET}", more=MAKE),
    case("an-awaited-own-result", body=f"var svc = await MakeAsync();\n{GET}",
         more=f"    Task<HttpService> MakeAsync() => Task.FromResult({NEW});"),
    case("a-closure-sees-its-functions-local",
         body=f"var svc = {NEW};\nFunc<Task> f = async () => {GET[:-1]};\nawait f();"),
    case("a-using-declaration", body=f"using var svc = {NEW};\n{GET}"),
    case("a-local-functions-parameter", members=OTHER_FIELD,
         body=f"async Task g(HttpService svc) => {GET[:-1]};\nawait g(null);"),
    case("a-lambda-parameter-shadows-a-field", members=OTHER_FIELD,
         body=f"Func<HttpService, Task> f = async (HttpService svc) => {GET[:-1]};\nawait f(null);"),
    case("a-block-local-before-the-use-in-its-block", members=OTHER_FIELD, body=f"{{\nvar svc = {NEW};\n{GET}\n}}"),
    case("a-field-a-base-class-declares", scanner="no type: only the class's own members",
         declaration=" : BaseClient", body=GET.replace("svc.", "_base.")),
    case("this-field", scanner="no type: a receiver that is not a name", members=FIELD,
         body=GET.replace("svc.", "this.svc.")),
    case("a-field-of-a-field", scanner="no type: a receiver that is not a name",
         members="    private readonly Holder h = new Holder();", body=GET.replace("svc.", "h.Svc.")),
    case("a-service-built-inline", scanner="no type: a receiver that is not a name", params="IServiceProvider sp",
         body=GET.replace("svc.", "sp.GetRequiredService<HttpService>().")),
    case("a-block-local-after-the-use", scanner="the block's local, declared after the use", members=FIELD,
         body=f"{GET}\n{{ var svc = new Other(); }}"),
    case("the-enclosing-class-shares-a-visible-name", resolver="no type: two visible types of that name",
         usings="using Api.Other;\n", members=FIELD, body=GET, files=HOMONYM),
    case("a-sibling-block-local-out-of-scope", resolver="the block's local", scanner="the block's local",
         members=FIELD, body=f"{{ var svc = new Other(); }}\n{GET}"),
    case("a-lambda-local-out-of-scope", resolver="the lambda's local", scanner="the lambda's local",
         members=FIELD, body=f"Action a = () => {{ var svc = new Other(); }};\n{GET}"),
    case("an-untyped-local-hides-a-field", resolver="the field's type", members=FIELD,
         body=f"var svc = Unknown();\n{GET}", edges=set(), calls=set()),
    case("an-implicit-lambda-parameter-hides-a-field", resolver="the field's type", scanner="the field's type",
         members=FIELD, body=f"Func<Other, Task> f = async svc => {GET[:-1]};\nawait f(null);", edges=set(),
         calls=set()),
    case("a-typeless-lambda-parameter-hides-a-local", resolver="the local's type",
         body=f"var svc = {NEW};\nFunc<Other, Task> f = async (svc) => {GET[:-1]};\nawait f(null);", edges=set(),
         calls=set()),
]


def _params(side: int):
    return [pytest.param(fields, expected, id=id, marks=pytest.mark.xfail(strict=True, reason=wrong) if wrong else ())
            for id, fields, expected, *wrong_on in CASES for wrong in [wrong_on[side]]]


def _extract(root, fields: dict):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    body = "\n".join(" " * 8 + line for line in fields.get("body", "").splitlines())
    client = CLIENT % ({"usings": "", "declaration": "", "members": "", "params": "", "more": ""}
                       | {k: v for k, v in fields.items() if k != "files"} | {"body": body})
    files = {"Api.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>', "Services/HttpService.cs": SERVICES,
             "Items/ItemsClient.cs": client, **fields.get("files", {})}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)))


@pytest.mark.parametrize("fields,expected", _params(0))
def test_a_call_reaches_the_method_of_the_declared_type(tmp_path, fields, expected):
    res, rv = _extract(tmp_path, fields)
    names = {s.id: s.qualified_name.removeprefix("Api.Services.") for s in res.symbols}
    found = {(names[c.callee_id], c.strategy) for c in rv.calls
             if names.get(c.caller_id, "").startswith("Api.Items.ItemsClient") and names.get(c.callee_id, "").endswith("HttpGet")}
    assert found == expected[0]


@pytest.mark.parametrize("fields,expected", _params(1))
def test_a_call_goes_through_the_wrapper_of_the_declared_type(tmp_path, fields, expected):
    res, _ = _extract(tmp_path, fields)
    assert {(c.method, c.path) for c in res.http_calls if "ItemsClient" in c.evidence} == expected[1]
