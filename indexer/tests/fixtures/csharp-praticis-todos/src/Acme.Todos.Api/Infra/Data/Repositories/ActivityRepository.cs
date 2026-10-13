using Acme.Todos.Api.Domain.Interfaces.Repositories;
using Acme.Todos.Api.Domain.Models;
using Acme.Todos.Api.Infra.Data.Context;
using Acme.Shared.Bus.Abstractions;
using Acme.Shared.Data.MongoDB.Repositories;

namespace Acme.Todos.Api.Infra.Data.Repositories;

public class ActivityRepository : BaseRepository<ActivityModel, Guid>, IActivityRepository, IActivityReadRepository
{
    private readonly IActivityReadRepository _readRepository;

    public ActivityRepository(TodosContext context, IServiceBus serviceBus, IActivityReadRepository readRepository)
        : base(context, serviceBus, readRepository, Collections.ACTIVITY)
        => this._readRepository = readRepository;

    public bool IsUniqueKey(string idempotencyKey)
        => this._readRepository.IsUniqueKey(idempotencyKey);
}
