using Acme.Reports.Core.Domain.Interfaces;
using Acme.Reports.Core.Domain.Models;
using Acme.Reports.Core.Infra.Data.Context;
using Acme.Shared.Bus.Abstractions;
using Acme.Shared.Data.MongoDB.Repositories;
using MongoDB.Driver;

namespace Acme.Reports.Core.Infra.Data.Repositories;

public class TodoRepository : BaseRepository<TodoModel, Guid>, ITodoRepository
{
    private readonly ITodoReadRepository _readRepository;

    public TodoRepository(ReportsContext context, IServiceBus serviceBus, ITodoReadRepository readRepository)
        : base(context, serviceBus, readRepository, Collections.TODO)
    {
        _readRepository = readRepository;
    }

    public async Task<bool> UpdateProgressAsync(Guid todoId, long amount, CancellationToken cancellationToken = default)
    {
        try
        {
            var filter = Builders<TodoModel>.Filter.Eq(x => x.Id, todoId);

            var update = Builders<TodoModel>.Update
                .Inc(x => x.Progress, amount);

            var options = new UpdateOptions { IsUpsert = true };

            var result = await this.Db.UpdateOneAsync(filter, update, options, cancellationToken);

            return result.IsAcknowledged;
        }
        catch (Exception e)
        {
            var msg = $"An error occurred while updating todo progress with ID: {todoId}.";
            await this.ServiceBus.PublishAsync(new SystemError(msg, e), cancellationToken);

            return false;
        }
    }
}
