using Flows.Abstractions;

namespace Flows.Endpoints.Definitions.List;

internal class List : FlowsEndpointWithoutRequest
{
    public override void Configure()
    {
        Get("/workflow-definitions");
        RequirePermission("definitions");
    }

    public override Task HandleAsync(CancellationToken cancellationToken) => Task.CompletedTask;
}
