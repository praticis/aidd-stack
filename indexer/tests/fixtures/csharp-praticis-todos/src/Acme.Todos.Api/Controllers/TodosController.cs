using System.Net;
using Acme.Todos.Api.Application.Commands.TodoCommands;
using Acme.Todos.Api.Application.Queries;
using Acme.Todos.Contracts.Requests.TodoRequests;
using Acme.Shared.Api.Response;
using Microsoft.AspNetCore.Mvc;

namespace Acme.Todos.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class TodosController(IServiceProvider provider) : InternalControllerBase(provider)
{
    private readonly ITodoQuery _query = provider.GetRequiredService<ITodoQuery>();

    [HttpPost]
    public async Task<IActionResult> CreateAsync(CreateTodoRequest request, CancellationToken cancellationToken)
    {
        base.PropagateContext();

        var result = await this.ServiceBus.SendAsync(new CreateTodoCommand(request), cancellationToken);

        return await this.ResponseAsync(result);
    }

    [HttpPut("{todoId:guid}")]
    public async Task<IActionResult> ChangeAsync(Guid todoId, [FromBody] UpdateTodoRequest request, CancellationToken cancellationToken)
    {
        base.PropagateContext();

        var result = await this.ServiceBus.SendAsync(new UpdateTodoCommand(todoId, request), cancellationToken);

        return await this.ResponseAsync(result);
    }

    [HttpGet]
    public async Task<IActionResult> ListAsync(CancellationToken cancellationToken)
    {
        var result = await this._query.ObtainsAllAsync(cancellationToken);

        return await this.ResponseAsync(result);
    }

    [HttpGet("{todoId:guid}/details")]
    public async Task<IActionResult> FindByIdAsync(Guid todoId, CancellationToken cancellationToken)
    {
        var result = await this._query.FindByIdAsync(todoId, cancellationToken);

        var statusCode = result is null ? HttpStatusCode.NotFound : HttpStatusCode.OK;

        return await this.ResponseAsync(statusCode, result);
    }
}
