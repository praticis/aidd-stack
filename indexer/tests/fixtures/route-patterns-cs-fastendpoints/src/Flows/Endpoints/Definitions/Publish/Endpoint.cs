using Flows.Abstractions;

namespace Flows.Endpoints.Definitions.Publish;

// two paths, the second a deprecated alias
internal class Publish : FlowsEndpoint<Request, Response>
{
    public override void Configure()
    {
        Post("/workflow-definitions/{definitionId}/publish", "/workflow-definitions/publish/{definitionId}");
    }

    public override Task HandleAsync(Request request, CancellationToken cancellationToken) => Task.CompletedTask;
}

internal class Request
{
    public string DefinitionId { get; set; } = "";
}

internal class Response
{
}
