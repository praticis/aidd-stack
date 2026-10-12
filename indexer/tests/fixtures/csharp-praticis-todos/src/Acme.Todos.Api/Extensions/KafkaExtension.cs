using Acme.Todos.Contracts.Events.TodoEvents;
using Acme.Todos.Contracts.Events.ActivityEvents;

namespace Microsoft.Extensions.DependencyInjection;

internal static class KafkaExtension
{
    internal static IServiceCollection AddKafka(this IServiceCollection services, IConfiguration config)
    {
        services.AddKafka(op =>
            {
                op.ConnectionString = config.GetConnectionString("KafkaConnection")!;
                op.ProducerConfigSection = config.GetSection("Kafka:Producers");

                op.SetAppNameFromDefaultConvention();
            }).AddProducers(cfg =>
            {
                cfg.AddProducer<ActivityWasCreatedEvent>();
                cfg.AddProducer<TodoWasCreatedEvent>();
            })
            .AddConsumers(cfg =>
            {

            }).Build();

        return services;
    }
}
