using Acme.Reports.Core.CommandHandlers.SummaryCommandHandlers;
using Acme.Reports.Core.Domain.Interfaces;
using Acme.Reports.Core.Infra.Data.Context;
using Acme.Reports.Core.Infra.Data.Repositories;
using Acme.Shared.Bus.Kafka;
using Acme.Shared.Data.MongoDB;

namespace Microsoft.Extensions.DependencyInjection;

public static class ServiceCollectionExtension
{
    public static IServiceCollection AddServices(this IServiceCollection services, IConfiguration config, IHostEnvironment env)
    {
        services.AddControllers();
        services.AddHttpContextAccessor();

        services.AddServiceBus(new []
        {
            typeof(Program).Assembly,
            typeof(ResetSummaryCommandHandler).Assembly,
            typeof(KafkaDistributedMessageEventHandler).Assembly,
        });

        services.AddKafka(config);
        services.AddDatabase(config);
        services.AddDistributedMemoryCache();
        services.AddOutboundHttpClients(config);
        services.AddCorrelation(env.EnvironmentName);
        services.AddProcessors();

        return services;
    }

    private static IServiceCollection AddDatabase(this IServiceCollection services, IConfiguration config)
    {
        var connection = config.GetConnectionString("MongoConnection")!;

        services.AddDbContext<ReportsContext>(op => op.UseConnectionString(connection));

        services.AddScoped<ITodoRepository, TodoRepository>();
        services.AddScoped<ITodoReadRepository, TodoReadRepository>();

        services.AddScoped<IActivityRepository, ActivityRepository>();
        services.AddScoped<IActivityReadRepository, ActivityReadRepository>();

        services.AddScoped<ITimelineRepository, TimelineRepository>();
        services.AddScoped<ITimelineReadRepository, TimelineReadRepository>();

        services.AddSingleton<ISummaryRepository, SummaryRepository>();

        return services;
    }
}
