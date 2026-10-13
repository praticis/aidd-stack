using Acme.Reports.Core.Processors.ActivityProcessors.RegisterActivityProcessor;

namespace Microsoft.Extensions.DependencyInjection;

public static class ProcessorExtension
{
    public static IServiceCollection AddProcessors(this IServiceCollection services)
    {
        services.AddRegisterActivityProcessor();

        return services;
    }

    // Decorator chain, outermost last: CheckTodoStep -> CommitActivityStep -> UpdateCacheStep.
    private static void AddRegisterActivityProcessor(this IServiceCollection services)
    {
        services.AddScoped<IRegisterActivityProcessor, UpdateCacheStep>();
        services.Decorate<IRegisterActivityProcessor, CommitActivityStep>();
        services.Decorate<IRegisterActivityProcessor, CheckTodoStep>();
    }
}
