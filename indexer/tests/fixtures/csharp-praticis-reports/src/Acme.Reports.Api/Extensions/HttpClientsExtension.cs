using Acme.Reports.Core.Infra.Http.Outbound.TodosApi;

namespace Microsoft.Extensions.DependencyInjection;

internal static class HttpClientsExtension
{
    internal static IServiceCollection AddOutboundHttpClients(this IServiceCollection services, IConfiguration config)
    {
        // env_hint: TODOS_API_URL; falls back to appsettings for local dev without the env var.
        var todosApiUrl = Environment.GetEnvironmentVariable("TODOS_API_URL")
            ?? config["TodosApi:BaseUrl"]
            ?? "http://localhost:5104";

        services.AddHttpClient<ITodosApiClient, TodosApiClient>("TodosApi", client =>
        {
            client.BaseAddress = new Uri(todosApiUrl);
        });

        return services;
    }
}
