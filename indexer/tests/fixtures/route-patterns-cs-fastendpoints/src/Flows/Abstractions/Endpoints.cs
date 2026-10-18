using FastEndpoints;

namespace Flows.Abstractions;

// Elsa's ElsaEndpoint<..>: the project's own bases over FastEndpoints', several of one name told apart by their type
// parameters.
public abstract class FlowsEndpointWithoutRequest : EndpointWithoutRequest
{
    protected void RequirePermission(string resource) { }
}

public abstract class FlowsEndpoint<TRequest> : Endpoint<TRequest> where TRequest : notnull
{
}

public abstract class FlowsEndpoint<TRequest, TResponse> : Endpoint<TRequest, TResponse> where TRequest : notnull where TResponse : notnull
{
}

// a second level of the project's own
public abstract class AdminEndpoint<TRequest, TResponse> : FlowsEndpoint<TRequest, TResponse> where TRequest : notnull where TResponse : notnull
{
}
