"""C#'s type service past a local's own declaration: a partial type is one type, whatever part declares a member or
names a base, and a local has the type the result of the method it is assigned from declares, on its own type or on
another. Both the resolver and the HTTP scanner ask it."""

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

public interface IFactory { HttpService Create(); }

public class Factory : IFactory
{
    public HttpService Create() => new HttpService(new HttpClient(), Urls.Base);
    public Task<HttpService> CreateAsync() => Task.FromResult(Create());
    public Other Make(int a) => new Other();
    public HttpService Make(string a) => Create();
    public Factory Self => this;
}

public class ChildFactory : Factory { }

public class BaseClient { protected HttpService _base = new HttpService(new HttpClient(), Urls.Base); }
"""
CLIENT = """using Api.Services;

namespace Api.Items;

public class Item {}

public %(partial)sclass ItemsClient%(declaration)s
{
%(members)s
    public async Task Run(%(params)s)
    {
%(body)s
    }
}
"""
PART = """using Api.Services;

namespace Api.Items;

public partial class ItemsClient%(declaration)s
{
%(members)s
}
"""
NEW = "new HttpService(new HttpClient(), Urls.Base)"
GET = 'await svc.HttpGet<Item>("items");'
TYPED = {("HttpService.HttpGet", "receiver-type")}
RESULT = pytest.mark.xfail(strict=True, reason="no type: a method's result is read only on the caller's own type")


def _extract(root, client: dict, part: dict | None = None, files: dict | None = None):
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    body = "\n".join(" " * 8 + line for line in client.get("body", "").splitlines())
    fields = {"partial": "partial " if part is not None else "", "declaration": "", "members": "", "params": ""}
    written = {"Api.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>', "Services/HttpService.cs": SERVICES,
               "Items/ItemsClient.cs": CLIENT % (fields | client | {"body": body}), **(files or {})}
    if part is not None:
        written["Items/ItemsClient.Part.cs"] = PART % ({"declaration": "", "members": ""} | part)
    for rel, text in written.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    with contextlib.redirect_stderr(io.StringIO()):
        return extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)))


def _edges(res, rv, ending: str = "HttpGet") -> set[tuple[str, str]]:
    names = {s.id: s.qualified_name.removeprefix("Api.Services.") for s in res.symbols}
    return {(names[c.callee_id], c.strategy) for c in rv.calls
            if names.get(c.caller_id, "").startswith("Api.Items.ItemsClient") and names.get(c.callee_id, "").endswith(ending)}


def _calls(res) -> set[tuple[str, str]]:
    return {(c.method, c.path) for c in res.http_calls if "ItemsClient" in c.evidence}


# -- a partial type is one type ---------------------------------------------------------------------------------------
PARTIAL = [
    pytest.param({"body": GET}, {"members": f"    private readonly HttpService svc = {NEW};"},
                 id="a-field-another-part-declares"),
    pytest.param({"body": GET.replace("svc.", "_base.")}, {"declaration": " : BaseClient"},
                 id="a-base-another-part-names"),
]


@pytest.mark.parametrize("client,part", PARTIAL)
def test_a_call_reaches_a_member_another_part_declares(tmp_path, client, part):
    assert _edges(*_extract(tmp_path, client, part)) == TYPED


@pytest.mark.parametrize("client,part", PARTIAL)
def test_a_wrapper_call_reaches_a_member_another_part_declares(tmp_path, client, part):
    res, _ = _extract(tmp_path, client, part)
    assert _calls(res) == {("GET", "/items")}


def test_two_types_of_one_name_that_are_not_partial_stay_apart(tmp_path):
    """Two projects that each declare the type: which one a file means cannot be told, so nothing is typed by it."""
    twin = {"Twin/ItemsClient.cs": "namespace Api.Items;\n\npublic class ItemsClient { private Other svc; }\n"}
    res, rv = _extract(tmp_path, {"members": f"    private readonly HttpService svc = {NEW};", "body": GET},
                       files=twin)
    assert not {e for e in _edges(res, rv) if e[1].startswith("receiver-type")}


# -- a local has the type its method's declared result gives it -------------------------------------------------------
RESULTS = [
    pytest.param({"params": "Factory factory", "body": f"var svc = factory.Create();\n{GET}"}, TYPED,
                 id="a-method-of-another-type", marks=RESULT),
    pytest.param({"params": "Factory factory", "body": f"var svc = await factory.CreateAsync();\n{GET}"}, TYPED,
                 id="an-awaited-task", marks=RESULT),
    pytest.param({"params": "IFactory factory", "body": f"var svc = factory.Create();\n{GET}"}, TYPED,
                 id="an-interfaces-method", marks=RESULT),
    pytest.param({"params": "ChildFactory factory", "body": f"var svc = factory.Create();\n{GET}"}, TYPED,
                 id="a-method-a-base-declares", marks=RESULT),
    pytest.param({"params": "Factory factory", "body": f"var svc = factory.Self.Create();\n{GET}"}, TYPED,
                 id="through-a-property", marks=RESULT),
    pytest.param({"members": "    private readonly Factory _factory = new Factory();",
                  "body": f"var svc = _factory.Create();\n{GET}"}, TYPED, id="on-a-field", marks=RESULT),
]


@pytest.mark.parametrize("client,edges", RESULTS)
def test_a_local_has_the_type_its_methods_result_declares(tmp_path, client, edges):
    assert _edges(*_extract(tmp_path, client)) == edges


@RESULT
def test_a_wrapper_call_on_a_local_a_method_returns(tmp_path):
    res, _ = _extract(tmp_path, {"params": "Factory factory", "body": f"var svc = factory.Create();\n{GET}"})
    assert _calls(res) == {("GET", "/items")}


def test_overloads_of_two_results_type_nothing(tmp_path):
    """`Make(int)` and `Make(string)` declare two results: which one the call gets needs its arguments' types."""
    res, rv = _extract(tmp_path, {"params": "Factory factory", "body": f'var svc = factory.Make("a");\n{GET}'})
    assert not {e for e in _edges(res, rv) if e[1].startswith("receiver-type")}
