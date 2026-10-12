using Acme.Shared.Data.MongoDB;
using Acme.Shared.Data.MongoDB.Builders;
using Acme.Shared.Data.MongoDB.Mappings;
using Acme.Shared.Data.MongoDB.Options;

namespace Acme.Todos.Api.Infra.Data.Context;

public class TodosContext(DbContextOptions options) : DbContext(options)
{
    protected override void OnModelCreating(ModelBuilder builder)
    {
        builder.ApplyEntityMapping(new IdentifiedObjectMap<Guid>());
    }
}
