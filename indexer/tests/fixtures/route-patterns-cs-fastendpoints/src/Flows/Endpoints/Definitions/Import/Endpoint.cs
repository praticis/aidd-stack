using Flows.Abstractions;

namespace Flows.Endpoints.Definitions.Import;

internal class Import : FlowsEndpoint<Request>
{
    public override void Configure()
    {
        Routes("workflow-definitions/import", "workflow-definitions/{definitionId}/import");
        Verbs(Http.POST, Http.PUT);
    }

    public override Task HandleAsync(Request request, CancellationToken cancellationToken) => Task.CompletedTask;
}

internal class Request
{
}
