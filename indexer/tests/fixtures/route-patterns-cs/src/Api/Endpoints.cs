using FastEndpoints;
using Ardalis.ApiEndpoints;
using Microsoft.AspNetCore.Mvc;

namespace Api.Orders;

// Every request class has a `Route`: `CreateOrderRequest.Route` is read by its qualified name.
public class CreateOrderRequest
{
    public const string Route = "/orders";
}

public class GetOrderRequest
{
    public const string Route = "/orders/{OrderId:int}";
    public int OrderId { get; set; }
}

public class CreateOrder : Endpoint<CreateOrderRequest, Results<Ok<OrderResponse>, ProblemHttpResult>>
{
    public override void Configure()
    {
        Post(CreateOrderRequest.Route);
        AllowAnonymous();
        Summary(s => s.Summary = "Create an order");
    }

    public override async Task HandleAsync(CreateOrderRequest req, CancellationToken ct) => await Send.OkAsync(ct);
}

public class GetOrder(IOrders orders) : Endpoint<GetOrderRequest, OrderResponse>
{
    public override void Configure()
    {
        Get(GetOrderRequest.Route);
    }

    public override async Task HandleAsync(GetOrderRequest req, CancellationToken ct) => await Send.OkAsync(ct);
}

public class Ping : EndpointWithoutRequest
{
    public override void Configure()
    {
        Verbs(Http.GET, Http.HEAD);
        Routes("/ping");
    }

    public override Task ExecuteAsync(CancellationToken ct) => Task.CompletedTask;
}

public class ListOrders : EndpointWithoutRequest<OrderList>
{
    public override void Configure()
    {
        Get($"/{nameof(Order)}s/recent");
    }

    public override Task HandleAsync(CancellationToken ct) => Task.CompletedTask;
}

// Ardalis.ApiEndpoints: a controller in all but name, routed by its action's attribute.
public class Authenticate : EndpointBaseAsync.WithRequest<AuthRequest>.WithActionResult<AuthResponse>
{
    [HttpPost("api/authenticate")]
    public override async Task<ActionResult<AuthResponse>> HandleAsync(AuthRequest request, CancellationToken ct = default) => Ok();
}

// Not an endpoint class: a `Get(...)` in a method called Configure is just a call.
public class CacheWarmup : BackgroundService
{
    public void Configure()
    {
        Get("/not-a-route");
    }
}
