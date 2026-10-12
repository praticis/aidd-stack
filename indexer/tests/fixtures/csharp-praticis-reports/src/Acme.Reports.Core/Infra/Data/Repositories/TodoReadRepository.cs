using Acme.Reports.Core.Domain.Interfaces;
using Acme.Reports.Core.Domain.Models;
using Acme.Reports.Core.Infra.Data.Context;
using Acme.Shared.Bus.Abstractions;
using Acme.Shared.Data.MongoDB.Repositories;

namespace Acme.Reports.Core.Infra.Data.Repositories;

public class TodoReadRepository : BaseReadRepository<TodoModel, Guid>, ITodoReadRepository
{
    public TodoReadRepository(ReportsContext context, IServiceBus serviceBus)
        : base(context, serviceBus, Collections.TODO)
    {
    }
}
