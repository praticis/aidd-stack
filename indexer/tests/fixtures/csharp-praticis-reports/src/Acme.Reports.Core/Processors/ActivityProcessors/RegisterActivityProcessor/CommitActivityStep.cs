using Acme.Reports.Core.Application.Events.ActivityEvents;
using Acme.Reports.Core.Domain.Interfaces;
using Acme.Reports.Core.Domain.Models;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Reports.Core.Processors.ActivityProcessors.RegisterActivityProcessor;

public class CommitActivityStep(IServiceProvider provider, IRegisterActivityProcessor processor) : IRegisterActivityProcessor
{
    private IActivityRepository _activityRepository = provider.GetRequiredService<IActivityRepository>();
    private readonly IServiceBus _serviceBus = provider.GetRequiredService<IServiceBus>();
    private readonly INotificationStore _store = provider.GetRequiredService<INotificationStore>();

    public async Task ProcessAsync(RegisterActivityTransfer transfer, CancellationToken cancellationToken)
    {
        var obj = transfer.Event.Activity;

        if (this._activityRepository.Exists(obj.ActivityId))
            return;

        var activity = new ActivityModel(obj.ActivityId, obj.TagId, obj.Title, obj.Value, obj.OccurredAt);

        await this._activityRepository.CreateAsync(activity, cancellationToken);

        if (this._store.HasNotifications())
            return;

        IEvent @event = new ActivityWasCommittedEvent(obj.TodoId, activity.TagId, obj.OccurredAt, activity.Value);
        await this._serviceBus.PublishAsync(@event, cancellationToken);

        if (this._store.HasNotifications())
        {
            activity.Rollback();
            return;
        }

        activity.Commit();
        await this._activityRepository.SaveAsync(activity, cancellationToken);

        await processor.ProcessAsync(transfer, cancellationToken);
    }

    public void Dispose()
    {
        this._activityRepository?.Dispose();
        this._activityRepository = null;
    }
}
