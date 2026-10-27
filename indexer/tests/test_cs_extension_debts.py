"""Calls to a C# extension method that the resolver still gets wrong. Each case states the right answer and is a strict
xfail with the reason: when the resolver learns it, the case passes, the xfail fails the suite, and the mark has to go.

What C# binds is the type's own member before any extension. The resolver has no members for a type outside the repo,
an untyped receiver reaches only extensions, and the count and the types of the arguments are not compared."""

import contextlib
import io

import pytest

HEADER = "namespace Api.Services;\n\n"


def _xfail(why: str):
    return pytest.mark.xfail(strict=True, reason=f"the resolver {why}")


def case(id, source, caller, expected, why):
    return pytest.param(source, caller, expected, id=id, marks=_xfail(why))


CASES = [
    case("an-extension-blocks-receiver-reaches-its-types-own-method",
         """public class Expr { }
public class Input<T> { public Expr Expression = new Expr(); }
public interface IEvaluator { Task<T?> Evaluate<T>(Expr expression); }

public static class EvaluatorExtensions
{
    extension(IEvaluator evaluator)
    {
        public Task<T?> Evaluate<T>(Input<T> input) => evaluator.Evaluate<T>(input.Expression);
    }
}
""", "Api.Services.EvaluatorExtensions.Evaluate", {("Api.Services.IEvaluator.Evaluate", "receiver-type")},
         "gives an extension block's receiver no type, so the call reaches only the block's own extension"),
    case("a-var-from-a-positional-records-property-has-its-type",
         """public class Expr { }
public class Input<T> { }
public interface IEvaluator { Task<T?> Evaluate<T>(Expr expression); }
public record Context(IEvaluator Evaluator);

public static class EvaluatorExtensions
{
    public static Task<T?> Evaluate<T>(this IEvaluator evaluator, Input<T> input) => default!;
}

public class Runner
{
    public async Task Run(Context context, Expr expression)
    {
        var evaluator = context.Evaluator;
        await evaluator.Evaluate<object>(expression);
    }
}
""", "Api.Services.Runner.Run", {("Api.Services.IEvaluator.Evaluate", "receiver-type")},
         "does not type a var taken from a positional record's property, so a generic call reaches only extensions"),
    case("an-outside-types-own-method-is-no-repo-extension",
         """public static class Readonlies
{
    public static IReadOnlyList<T> AsReadOnly<T>(this IEnumerable<T> source) => null!;
}

public class Runner
{
    public void Run(List<string> items) { items.AsReadOnly(); }
}
""", "Api.Services.Runner.Run", set(),
         "knows no members of a type outside the repo, so an extension on an interface is taken for List<T>.AsReadOnly()"),
    case("a-member-reached-through-a-package-type-has-its-own-method",
         """public static class CacheExtensions
{
    public static bool TryGetValue(this IDistributedCache cache, string key) => false;
}

public class Runner
{
    public void Run(HttpContext context) { context.Request.Headers.TryGetValue("key"); }
}
""", "Api.Services.Runner.Run", set(),
         "gives a member reached through a package's type no type, so an extension on an interface is taken for it"),
    case("the-arguments-types-tell-the-overloads-of-one-arity-apart",
         """public static class EndpointExtensions
{
    public static void MapGet(this IEndpointRouteBuilder builder, Delegate handler, string pattern) { }
}

public class Runner
{
    public void Run(WebApplication app, Delegate handler) { app.MapGet("/items", handler); }
}
""", "Api.Services.Runner.Run", set(),
         "does not compare the arguments' types, so the repo's overload is taken for the framework's of the same arity"),
    case("an-extension-of-a-predefined-type-is-not-taken-for-another-types-method",
         """public static class Texts
{
    public static string Reverse(this string text) => text;
}

public class Runner
{
    public void Run(List<int> items) { items.Reverse(); }
}
""", "Api.Services.Runner.Run", set(),
         "has no name for a predefined type in the type facts, so `this string` is taken for any receiver"),
    case("a-call-with-two-type-arguments-reaches-only-the-overload-with-two",
         """public static class OneAdder
{
    public static void Add<T>(this HttpClient http) { }
}

public static class TwoAdder
{
    public static void Add<T, U>(this HttpClient http) { }
}

public class Runner
{
    public void Run(HttpClient http) { http.Add<string, int>(); }
}
""", "Api.Services.Runner.Run", {("Api.Services.TwoAdder.Add", "same-file")},
         "checks that a method declares type parameters, not how many"),
]


def _edges(root, source: str, caller: str) -> set[tuple[str, str]]:
    from aidd_indexer.cli import extract_and_resolve
    from aidd_indexer.core.model import RepoInfo
    files = {"Api.csproj": '<Project Sdk="Microsoft.NET.Sdk"></Project>', "Services/Source.cs": HEADER + source}
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
