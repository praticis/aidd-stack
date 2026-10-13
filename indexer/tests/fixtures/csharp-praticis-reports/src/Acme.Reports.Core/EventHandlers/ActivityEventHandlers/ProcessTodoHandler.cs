using Acme.Reports.Core.Application.Events.ActivityEvents;
using Acme.Reports.Core.Domain.Interfaces;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Reports.Core.EventHandlers.ActivityEventHandlers;

public class ProcessTodoHandler(IServiceProvider provider) : IEventHandler<ActivityWasCommittedEvent>
{
    private ITodoRepository _todoRepository = provider.GetRequiredService<ITodoRepository>();

    public async Task Handle(ActivityWasCommittedEvent notification, CancellationToken cancellationToken)
    {
        await this._todoRepository.UpdateProgressAsync(notification.TodoId, notification.Value, cancellationToken);

        // TODO: Add event sourcing to enable reliable rollback
    }

    public void Dispose()
    {
        this._todoRepository?.Dispose();
        this._todoRepository = null;
    }
}
