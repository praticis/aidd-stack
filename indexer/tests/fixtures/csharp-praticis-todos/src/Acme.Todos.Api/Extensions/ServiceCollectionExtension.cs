using Acme.Shared.Bus.Kafka;
using Microsoft.AspNetCore.Mvc;
using Newtonsoft.Json;
using Newtonsoft.Json.Converters;

namespace Microsoft.Extensions.DependencyInjection;

public static class ServiceCollectionExtension
{
    public static IServiceCollection AddServices(this IServiceCollection services, IConfiguration config, IHostEnvironment env)
    {
        services.AddOpenApi();

        services.AddControllers()
            .AddNewtonsoftJson(options =>
            {
                options.SerializerSettings.ReferenceLoopHandling = ReferenceLoopHandling.Ignore;
                options.SerializerSettings.NullValueHandling = NullValueHandling.Ignore;
                options.SerializerSettings.Converters.Add(new StringEnumConverter());
            });

        services.Configure<ApiBehaviorOptions>(op =>
        {
            op.SuppressModelStateInvalidFilter = true;
        });

        services.AddServiceBus(new[]
        {
            typeof(Program).Assembly,
            typeof(KafkaDistributedMessageEventHandler).Assembly,
        });

        services.AddKafka(config);
        services.AddDatabase(config);

        services.AddHttpContextAccessor();
        services.AddCorrelation(env.EnvironmentName);

        return services;
    }
}
