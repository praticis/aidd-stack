"""What a name means in C#, where the resolver still reads it wrongly or not at all. Each case states the right answer
and is a strict xfail with the reason: when the resolver learns it, the case passes, the xfail fails the suite, and the
mark has to go.

Every case has a homonym of the right method in another type, because a call that goes by name reaches the right method
by luck when it is the only one of its name."""

import contextlib
import io

import pytest

HEADER = "namespace Api.Services;\n\n"
CSPROJ = '<Project Sdk="Microsoft.NET.Sdk"></Project>'
ITEM = "public class Item { public void Touch() { } }\npublic class Other { public void Touch() { } }\n"
TOUCH = ("Api.Services.Item.Touch", "receiver-type")


def _xfail(why: str):
    return pytest.mark.xfail(strict=True, reason=f"the resolver {why}")


def case(id, source, expected, why, caller="Api.Services.Runner.Run"):
    return pytest.param(source, caller, expected, id=id, marks=_xfail(why))


def runner(members: str, body: str = "", declaration: str = "") -> str:
    return f"{ITEM}\npublic class Runner{declaration}\n{{\n{members}\n    public void Run(){{ {body} }}\n}}\n"


LEGACY = {"Legacy.cs": "namespace Api.Legacy;\n\npublic class Clock { public void Tick() { } }\n"}
MODERN = {"Modern.cs": "namespace Api.Modern;\n\npublic class Clock { public void Tick() { } }\n"}
LEGACY_TICK = {("Api.Legacy.Clock.Tick", "receiver-type")}


def repo(files: dict[str, str], csproj: str = CSPROJ) -> dict[str, str]:
    return {"Api.csproj": csproj, **files}


def runner_file(usings: str, body: str, params: str = "Clock clock") -> dict[str, str]:
    return {"Runner.cs": f"{usings}\n\nnamespace Api.Services;\n\npublic class Runner\n{{\n"
                         f"    public void Run({params}) {{ {body} }}\n}}\n"}


def project(name: str, source: str, references: str = "") -> dict[str, str]:
    csproj = f'<Project Sdk="Microsoft.NET.Sdk">{references}</Project>'
    return {f"{name}/{name}.csproj": csproj, f"{name}/Source.cs": source}


CASES = [
    case("a-foreach-variable-has-the-elements-type",
         ITEM + "public class Runner\n{\n    public void Run(List<Item> items) { foreach (var item in items) item.Touch(); }\n}\n",
         {TOUCH}, "does not type a foreach variable, so its call goes by name"),
    case("an-out-var-has-the-parameters-type",
         ITEM + "public class Runner\n{\n    void Make(out Item made) { made = new Item(); }\n"
         "    public void Run() { Make(out var item); item.Touch(); }\n}\n",
         {TOUCH, ("Api.Services.Runner.Make", "same-file")}, "does not type an out var, so its call goes by name"),
    case("a-pattern-variable-has-the-patterns-type",
         ITEM + "public class Runner\n{\n    public void Run(object value) { if (value is Item item) item.Touch(); }\n}\n",
         {TOUCH}, "does not type a pattern variable, so its call goes by name"),
    case("a-lambda-parameter-has-the-delegates-type",
         ITEM + "public class Runner\n{\n    void Each(Action<Item> action) { }\n"
         "    public void Run() { Each(item => item.Touch()); }\n}\n",
         {TOUCH, ("Api.Services.Runner.Each", "same-file")}, "does not type a lambda parameter, so its call goes by name"),
    case("an-extension-of-an-interface-binds-a-type-with-a-base-outside-the-repo",
         "public class Settings : Dictionary<string, string> { }\n"
         "public static class DictionaryExtensions\n{\n"
         "    public static string GetOrDefault(this IDictionary<string, string> map, string key, string fallback) => fallback;\n}\n"
         "public class Runner\n{\n    public void Run(Settings settings) { settings.GetOrDefault(\"a\", \"b\"); }\n}\n",
         {("Api.Services.DictionaryExtensions.GetOrDefault", "same-file")},
         "does not reach an extension for a type with a base outside the repo, which may declare the method"),
    case("a-field-with-type-arguments-passes-them-down-the-chain",
         ITEM + "public class Provider<T> { public T Sut { get; } }\npublic class Runner\n{\n"
         "    private readonly Provider<Item> _provider = new();\n    public void Run() { _provider.Sut.Touch(); }\n}\n",
         {TOUCH}, "keeps a member's type by its simple name, so a field loses its type arguments"),
    case("a-methods-own-type-parameter-takes-the-call-type-argument",
         ITEM + "public class Locator { public T Get<T>() => default!; }\npublic class Runner\n{\n"
         "    public void Run(Locator locator) { var item = locator.Get<Item>(); item.Touch(); }\n}\n",
         {TOUCH, ("Api.Services.Locator.Get", "receiver-type")}, "reads only the DI's GetRequiredService<T>() for a method's type parameter"),
    case("a-type-parameter-with-two-constraints-has-the-members-of-both",
         "public interface IFirst { void Alpha(); }\npublic interface ISecond { void Beta(); }\n"
         "public class Other { public void Beta() { } }\npublic class Runner\n{\n"
         "    public void Run<T>(T value) where T : IFirst, ISecond { value.Beta(); }\n}\n",
         {("Api.Services.ISecond.Beta", "receiver-type")}, "gives a type parameter with two constraints no type"),
    case("a-nested-type-argument-keeps-its-own-arguments",
         ITEM + "public class Box<T> { public T Value { get; } }\npublic abstract class Generic<TService> { protected TService Http { get; } }\n"
         "public class Runner : Generic<Box<Item>>\n{\n    public void Run() { Http.Value.Touch(); }\n}\n",
         {TOUCH}, "keeps only the outer name of a nested type argument, so Box<Item> passes Box"),
    case("the-extension-whose-this-is-the-receiver-wins-over-an-interfaces",
         "public static class ArrayExtensions\n{\n    public static bool IsNone<T>(this T[]? values) => true;\n}\n"
         "public static class EnumerableExtensions\n{\n    public static bool IsNone<T>(this IEnumerable<T>? values) => true;\n}\n"
         "public class Runner\n{\n    public void Run(int[] numbers) { numbers.IsNone(); }\n}\n",
         {("Api.Services.ArrayExtensions.IsNone", "same-file")},
         "does not prefer the extension whose this names the receiver's type to one that takes an interface"),
    case("an-array-has-no-extension-of-an-interface-it-does-not-implement",
         "public static class RuleExtensions\n{\n    public static IQueryable<T> Where<T>(this IQueryable<T> source, string rule) => source;\n}\n"
         "public class Runner\n{\n    public void Run(int[] numbers) { numbers.Where(n => n > 1); }\n}\n",
         set(), "takes an extension on an interface for any receiver outside the repo, an array included"),
    case("a-database-of-a-base-outside-the-repo-is-no-method-of-this-type",
         "public class OrderingContext : DbContext\n{\n    public Task BeginTransactionAsync() => Task.CompletedTask;\n"
         "    public Task Run() => Database.BeginTransactionAsync(IsolationLevel.ReadCommitted);\n}\n",
         set(), "reads a capitalized name a base outside the repo may declare as a type, and its call as this type's",
         caller="Api.Services.OrderingContext.Run"),
    case("a-registration-counts-for-the-project-that-runs-it",
         {**project("Shared", "namespace Shared;\n\npublic interface IImages { string Url(string name); }\n"),
          **project("Web", "namespace Web;\n\nusing Shared;\n\npublic class Images : IImages { public string Url(string name) => name; }\n"
                    "public static class Setup\n{\n    public static void Add(IServiceCollection services) { services.AddSingleton<IImages, Images>(); }\n}\n"
                    "public class Runner\n{\n    private readonly IImages _images;\n    public Runner(IImages images) { _images = images; }\n"
                    "    public void Run() { _images.Url(\"a\"); }\n}\n",
                    '<ItemGroup><ProjectReference Include="../Shared/Shared.csproj" /></ItemGroup>'),
          **project("Hybrid", "namespace Hybrid;\n\nusing Shared;\n\npublic class Images : IImages { public string Url(string name) => name; }\n"
                    "public static class Setup\n{\n    public static void Add(IServiceCollection services) { services.AddSingleton<IImages, Images>(); }\n}\n",
                    '<ItemGroup><ProjectReference Include="../Shared/Shared.csproj" /></ItemGroup>')},
         {("Shared.IImages.Url", "receiver-type"), ("Web.Images.Url", "receiver-type-impl")},
         "counts a registration for the whole repo, so an interface two projects register has no single implementation",
         caller="Web.Runner.Run"),
    case("an-alias-using-names-the-type",
         repo({**LEGACY, **MODERN, **runner_file("using Timer = Api.Legacy.Clock;", "timer.Tick();", "Timer timer")}),
         LEGACY_TICK, "does not read an alias using, so the type it names is unknown"),
    case("a-using-static-brings-the-types-static-methods",
         repo({"Util.cs": "namespace Api.Legacy;\n\npublic static class Util { public static void Help() { } }\n",
               "Helper.cs": "namespace Api.Modern;\n\npublic static class Helper { public static void Help() { } }\n",
               **runner_file("using static Api.Legacy.Util;", "Help();", "")}),
         {("Api.Legacy.Util.Help", "same-module")}, "reads a using static as a namespace, not as the static methods of a type"),
    case("an-msbuild-using-is-a-global-using",
         repo({**LEGACY, **MODERN, **runner_file("", "clock.Tick();")},
              '<Project Sdk="Microsoft.NET.Sdk"><ItemGroup><Using Include="Api.Legacy" /></ItemGroup></Project>'),
         LEGACY_TICK, "does not read a Using of the project file as a global using"),
    case("a-nested-block-namespace-is-named-with-the-one-around-it",
         repo({"Legacy.cs": "namespace Api\n{\n    namespace Legacy\n    {\n        public class Clock { public void Tick() { } }\n    }\n}\n",
               **MODERN, **runner_file("using Api.Legacy;", "clock.Tick();")}),
         LEGACY_TICK, "names a namespace nested in a block one without the one around it"),
    case("this-field-of-a-base-two-levels-up-has-its-type",
         ITEM + "public abstract class Root { protected Item _item = new Item(); }\npublic abstract class Middle : Root { }\n"
         "public class Runner : Middle\n{\n    public void Run() { this._item.Touch(); }\n}\n",
         {TOUCH}, "looks one base up for a field, where a member reads the whole chain"),
    case("a-namespace-of-an-unreferenced-project-is-not-seen",
         {**project("A", "namespace Shared;\n\npublic class Clock { public void Tick() { } }\n"),
          **project("B", "namespace Other;\n\npublic class Clock { public void Tick() { } }\n"),
          **project("C", "using Other;\nusing Shared;\n\nnamespace App;\n\npublic class Marker { }\n"
                         "public class Runner\n{\n    public void Run(Clock clock) { clock.Tick(); }\n}\n",
                    '<ItemGroup><ProjectReference Include="../B/B.csproj" /></ItemGroup>'),
          "C/Shared.cs": "namespace Shared;\n\npublic class Marker { }\n"},
         {("Other.Clock.Tick", "receiver-type")},
         "sees a namespaced type of a project the file's project does not reference", caller="App.Runner.Run"),
    case("an-extension-blocks-static-member-is-called-on-the-type",
         "public class Item { }\npublic class Other { public static Item Create() => new Item(); }\n"
         "public static class ItemExtensions\n{\n    extension(Item)\n    {\n        public static Item Create() => new Item();\n    }\n}\n"
         "public class Runner\n{\n    public Item Run() => Item.Create();\n}\n",
         {("Api.Services.ItemExtensions.Create", "same-file")}, "reads only the instance members of an extension block"),
    case("an-array-element-has-the-element-type",
         ITEM + "public class Runner\n{\n    public void Run(Item[] items) { items[0].Touch(); }\n}\n",
         {TOUCH}, "does not type an array's element, so its call goes by name"),
    case("a-foreach-over-an-array-has-the-element-type",
         ITEM + "public class Runner\n{\n    public void Run(Item[] items) { foreach (var item in items) item.Touch(); }\n}\n",
         {TOUCH}, "does not type a foreach variable over an array, so its call goes by name"),
]


def _edges(root, files, caller: str) -> set[tuple[str, str]]:
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    if isinstance(files, str):
        files = {"Api.csproj": CSPROJ, "Services/Source.cs": HEADER + files}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    with contextlib.redirect_stderr(io.StringIO()):
        res, rv = extract_and_resolve(RepoInfo(tenant="t", name="repo", ref="main", commit_sha="x", root=str(root)))
    names = {s.id: s.qualified_name for s in res.symbols}
    return {(names[c.callee_id], c.strategy) for c in rv.calls if names.get(c.caller_id) == caller}


@pytest.mark.parametrize("source,caller,expected", CASES)
def test_the_call_reaches_what_csharp_binds(tmp_path, source, caller, expected):
    assert _edges(tmp_path, source, caller) == expected
