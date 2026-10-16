using Microsoft.AspNetCore.Mvc;
using Shop.Api.Infra;
using Shop.Api.Queries;

namespace Shop.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class AccountsController(IServiceProvider provider) : ControllerBase
{
    private readonly IAccountQuery _query = provider.GetRequiredService<IAccountQuery>();
    private GroupReadRepository Groups { get; } = new();
    private readonly IAccountReadRepository _accounts = provider.GetRequiredService<IAccountReadRepository>();

    [HttpGet("{id:guid}/details")]
    public async Task<IActionResult> FindByIdAsync(Guid id, CancellationToken ct)
    {
        var result = await this._query.FindByIdAsync(id, ct);          // field of interface type -> interface + unique implementer
        var count = await Groups.CountAsync();                          // property; method inherited from an in-repo base class
        var local = new GroupReadRepository();
        var desc = local.Describe();                                    // local `new T()`
        var model = await _accounts.FindByIdAsync(id, ct);              // inherited from a package interface: must NOT hit IAccountQuery's explicit impl
        return Ok(new { result, count, desc });
    }

    public string Describe() => "controller";                          // homonym: must NOT be chosen for local.Describe()

    public async Task<int> Lookup(Guid id, CancellationToken ct)
    {
        var query = provider.GetRequiredService<IAccountQuery>();       // `var` typed by the DI call
        var direct = await provider.GetRequiredService<IAccountQuery>().FindByIdAsync(id, ct);   // chained on the DI call
        Func<Task<object?>> later = async () => await query.FindByIdAsync(id, ct);              // closure: the local is outside
        var found = await Groups.FindAsync<string>(id);                 // generic method on a receiver
        var label = this.Label<int>();                                  // generic method on `this`
        return direct is null ? 0 : 1;
    }

    private string Label<T>() => typeof(T).Name;

    public static void Wire(IServiceCollection services)
    {
        var fake = Substitute.For<IAccountQuery>();                     // a package's static type: not the repo's `For`
        services.AddInfra();                                            // the repo's extension method on a package type
        Guid? id = null;
        var empty = id.IsNullOrEmpty();                                 // an extension method with an attribute on `this`
        var msg = Shop.Api.Infra.Messages.For("denied");                // a repo type named through its namespace
        Make().Configure<int>();                                        // a generic method on a receiver of unknown type
        services.AddReadModels(cached: true);                           // an extension method declared over lines
        var http = new HttpClient();
        _ = http.GetAsync("/health");                                   // HttpClient's own: not the repo's extension on another type
        _ = Make().GetAsync<int>("/x");                                 // unknown receiver: not an extension of a concrete type
        List<string> names = new();
        names.Add("a");                                                 // List's own Add: no repo method
        _ = names.Contains("a");                                        // List's own Contains: the extension takes 2 arguments
        _ = names.Contains("a", StringComparison.Ordinal);              // the repo's extension
    }

    private static object Make() => new();

    public string Caller() => HttpContext.RemoteIp();                  // ControllerBase's HttpContext: inherited, not static
}
