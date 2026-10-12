using Acme.Reports.Core.Domain.Interfaces;
using Acme.Reports.Core.Domain.Models;
using Acme.Reports.Core.Infra.Data.Context;
using Acme.Shared.Bus.Abstractions;
using Acme.Shared.Data.MongoDB.Repositories;

namespace Acme.Reports.Core.Infra.Data.Repositories;

public class ActivityRepository : BaseRepository<ActivityModel, Guid>, IActivityRepository
{
    public ActivityRepository(ReportsContext context, IServiceBus serviceBus, IActivityReadRepository readRepository)
        : base(context, serviceBus, readRepository, Collections.ACTIVITY)
    {
    }
}
