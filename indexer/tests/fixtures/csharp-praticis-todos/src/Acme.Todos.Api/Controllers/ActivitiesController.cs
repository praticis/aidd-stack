using Acme.Todos.Api.Application.Commands.ActivityCommands;
using Acme.Todos.Contracts.Requests.ActivityRequests;
using Acme.Shared.Api.Response;
using Microsoft.AspNetCore.Mvc;

namespace Acme.Todos.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class ActivitiesController(IServiceProvider provider) : InternalControllerBase(provider)
{
    [HttpPost]
    public async Task<IActionResult> RegisterActivityAsync([FromBody] RegisterActivityRequest request, CancellationToken cancellationToken)
    {
        base.PropagateContext();

        var result = await this.ServiceBus.SendAsync(new RegisterActivityCommand(request), cancellationToken);

        return await base.ResponseAsync(result);
    }
}
