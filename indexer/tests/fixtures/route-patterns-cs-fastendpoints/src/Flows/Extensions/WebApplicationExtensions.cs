using FastEndpoints;

namespace Flows.Extensions;

// Elsa's WebApplicationExtensions: the global RoutePrefix through a parameter of a private helper, whose callers take
// it from their own parameter's default.
public static class WebApplicationExtensions
{
    public static IApplicationBuilder UseFlowsApi(this IApplicationBuilder app, string routePrefix = "flows/api")
    {
        return app.UseFastEndpoints(config => ConfigureFlowsApi(config, routePrefix));
    }

    public static IEndpointRouteBuilder MapFlowsApi(this IEndpointRouteBuilder routes, string routePrefix = "flows/api") =>
        routes.MapFastEndpoints(config => ConfigureFlowsApi(config, routePrefix));

    private static void ConfigureFlowsApi(Config config, string routePrefix)
    {
        config.Endpoints.RoutePrefix = routePrefix;
    }
}
