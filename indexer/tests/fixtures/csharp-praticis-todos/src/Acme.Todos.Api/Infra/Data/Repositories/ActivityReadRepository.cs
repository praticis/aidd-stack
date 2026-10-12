using Acme.Todos.Api.Application.Queries;
using Acme.Todos.Api.Domain.Interfaces.Repositories;
using Acme.Todos.Api.Domain.Models;
using Acme.Todos.Api.Infra.Data.Context;
using Acme.Shared.Bus.Abstractions;
using Acme.Shared.Data.MongoDB.Repositories;

namespace Acme.Todos.Api.Infra.Data.Repositories;

public class ActivityReadRepository : BaseReadRepository<ActivityModel, Guid>, IActivityReadRepository, IActivityQuery
{
    public ActivityReadRepository(TodosContext context, IServiceBus serviceBus)
        : base(context, serviceBus, Collections.ACTIVITY)
    { }

    public bool IsUniqueKey(string idempotencyKey) => this.NotExists(t => t.IdempotencyKey == idempotencyKey);
}
