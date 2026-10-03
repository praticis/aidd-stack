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
}
