using System.Net;
using Acme.Projects.Application.Commands.ProjectCommands;
using Acme.Projects.Application.Queries;
using Acme.Projects.Contracts.Requests.ProjectRequests;
using Acme.Shared.Api.Response;
using Microsoft.AspNetCore.Mvc;

namespace Acme.Projects.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class ProjectsController(IServiceProvider provider) : InternalControllerBase(provider)
{
    private readonly IProjectQuery _query = provider.GetRequiredService<IProjectQuery>();

    [HttpPost]
    public async Task<IActionResult> CreateAsync(CreateProjectRequest request, CancellationToken cancellationToken)
    {
        base.PropagateContext();

        var result = await this.ServiceBus.SendAsync(new CreateProjectCommand(request), cancellationToken);

        return await this.ResponseAsync(result);
    }

    [HttpPut("{projectId:guid}/archive")]
    public async Task<IActionResult> ArchiveAsync(Guid projectId, CancellationToken cancellationToken)
    {
        base.PropagateContext();

        var result = await this.ServiceBus.SendAsync(new ArchiveProjectCommand(projectId), cancellationToken);

        return await this.ResponseAsync(result);
    }

    [HttpGet("{projectId:guid}/details")]
    public async Task<IActionResult> FindByIdAsync(Guid projectId, CancellationToken cancellationToken)
    {
        var result = await this._query.FindByIdAsync(projectId, cancellationToken);

        var statusCode = result is null ? HttpStatusCode.NotFound : HttpStatusCode.OK;

        return await this.ResponseAsync(statusCode, result);
    }
}
