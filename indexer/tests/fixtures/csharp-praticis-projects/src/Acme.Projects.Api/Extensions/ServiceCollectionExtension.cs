using Acme.Projects.Application.Commands.ProjectCommands;
using Acme.Projects.Application.Queries;
using Acme.Projects.Core.CommandHandlers.ProjectCommandHandlers;
using Acme.Projects.Domain.Interfaces;
using Acme.Projects.Infra.Data.Context;
using Acme.Projects.Infra.Data.Repositories;
using Acme.Projects.Infra.Http.Outbound.TodosApi;
using Acme.Shared.Bus.Kafka;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace Microsoft.Extensions.DependencyInjection;

public static class ServiceCollectionExtension
{
    public static IServiceCollection AddServices(this IServiceCollection services, IConfiguration config, IHostEnvironment env)
    {
        services.AddOpenApi();
        services.AddControllers();

        services.Configure<ApiBehaviorOptions>(op =>
        {
            op.SuppressModelStateInvalidFilter = true;
        });

        services.AddServiceBus(new[]
        {
            typeof(Program).Assembly,
            typeof(CreateProjectCommand).Assembly,
            typeof(CreateProjectCommandHandler).Assembly,
            typeof(KafkaDistributedMessageEventHandler).Assembly,
        });

        services.AddKafka(config);
        services.AddDatabase(config);
        services.AddOutboundHttpClients(config);

        services.AddHttpContextAccessor();
        services.AddCorrelation(env.EnvironmentName);

        return services;
    }

    public static IServiceCollection AddDatabase(this IServiceCollection services, IConfiguration config)
    {
        services.AddDbContext<ProjectsContext>(options => options.UseNpgsql(config.GetConnectionString("Projects")));

        services.AddScoped<IProjectReadRepository, ProjectReadRepository>();
        services.AddScoped<IProjectQuery, ProjectReadRepository>();
        services.AddScoped<IProjectRepository, ProjectRepository>();

        return services;
    }

    public static IServiceCollection AddOutboundHttpClients(this IServiceCollection services, IConfiguration config)
    {
        services.AddHttpClient<ITodosApiClient, TodosApiClient>("TodosApi", client =>
        {
            client.BaseAddress = new Uri(config["TodosApi:BaseUrl"]!);
        });

        return services;
    }
}
