using Flows.Abstractions;

namespace Flows.Endpoints.Definitions.Execute;

// the routes before the verbs, the verb by FastEndpoints' qualified name; two levels of the project's bases
internal class Execute : AdminEndpoint<Request, Response>
{
    public override void Configure()
    {
        Routes("/workflow-definitions/{definitionId}/execute");
        Verbs(FastEndpoints.Http.POST);
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
