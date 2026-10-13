using Acme.Reports.Core.Domain.Interfaces;
using Acme.Reports.Core.Domain.Models;
using Acme.Reports.Core.Infra.Data.Context;
using Acme.Shared.Bus.Abstractions;
using Acme.Shared.Data.MongoDB.Repositories;
using MongoDB.Driver;

namespace Acme.Reports.Core.Infra.Data.Repositories;

public class TimelineRepository : BaseRepository<TimelineModel, long>, ITimelineRepository
{
    public TimelineRepository(ReportsContext context, IServiceBus serviceBus, ITimelineReadRepository readRepository)
        : base(context, serviceBus, readRepository, Collections.TIMELINE)
    {
    }

    public override async Task<bool> SaveAsync(TimelineModel model, CancellationToken cancellationToken = default)
    {
        try
        {
            var filter = Builders<TimelineModel>.Filter.Eq(x => x.Id, model.Id);

            var update = Builders<TimelineModel>.Update
                .Inc(x => x.Value, model.Value)
                .SetOnInsert(x => x.Id, model.Id)
                .SetOnInsert(x => x.ReferenceId, model.ReferenceId)
                .SetOnInsert(x => x.EffectiveDay, model.EffectiveDay);

            var options = new UpdateOptions { IsUpsert = true };

            var result = await this.Db.UpdateOneAsync(filter, update, options, cancellationToken);

            return result.IsAcknowledged;
        }
        catch (Exception e)
        {
            var msg = $"An error occurred while updating a model of type {nameof(TimelineModel)} with ID: {model.Id}.";
            await this.ServiceBus.PublishAsync(new SystemError(msg, e), cancellationToken);

            return false;
        }
    }
}
