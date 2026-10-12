using Acme.Reports.Core.Processors.ActivityProcessors.RegisterActivityProcessor;
using Acme.Shared.Bus.Abstractions;
using Acme.Todos.Contracts.Events.ActivityEvents;

namespace Acme.Reports.Api.Consumers;

public class ActivityWasCreatedEventHandler(IServiceProvider provider) : IEventHandler<ActivityWasCreatedEvent>
{
    private IRegisterActivityProcessor _processor = provider.GetRequiredService<IRegisterActivityProcessor>();
    private readonly INotificationStore _store = provider.GetRequiredService<INotificationStore>();

    public async Task Handle(ActivityWasCreatedEvent notification, CancellationToken cancellationToken)
    {
        await this._processor.ProcessAsync(new RegisterActivityTransfer(notification), cancellationToken);

        if (!this._store.HasNotifications())
            return;

        // TODO: DLQ and retry
    }

    public void Dispose()
    {
        this._processor?.Dispose();
        this._processor = null;
    }
}
