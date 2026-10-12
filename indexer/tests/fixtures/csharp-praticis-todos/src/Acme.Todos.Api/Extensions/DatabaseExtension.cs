using Acme.Todos.Api.Application.Queries;
using Acme.Todos.Api.Domain.Interfaces.Repositories;
using Acme.Todos.Api.Infra.Data.Context;
using Acme.Todos.Api.Infra.Data.Repositories;
using Acme.Shared.Data.MongoDB;
using MongoDB.Bson;
using MongoDB.Bson.Serialization;
using MongoDB.Bson.Serialization.Serializers;

namespace Microsoft.Extensions.DependencyInjection;

internal static class DatabaseExtension
{
    internal static IServiceCollection AddDatabase(this IServiceCollection services, IConfiguration config)
    {
        var connection = config.GetConnectionString("MongoConnection")!;

        BsonSerializer.RegisterSerializer(new GuidSerializer(GuidRepresentation.Standard));

        services.AddDbContext<TodosContext>(op => op.UseConnectionString(connection));

        services.AddScoped<ITodoRepository, TodoRepository>();
        services.AddScoped<ITodoReadRepository, TodoReadRepository>();
        services.AddScoped<ITodoQuery, TodoReadRepository>();

        services.AddScoped<IActivityRepository, ActivityRepository>();
        services.AddScoped<IActivityReadRepository, ActivityReadRepository>();
        services.AddScoped<IActivityQuery, ActivityReadRepository>();

        return services;
    }
}
