using Acme.Reports.Core.Application.Events.ActivityEvents;
using Acme.Reports.Core.Domain.Interfaces;
using Acme.Reports.Core.Domain.Models;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Reports.Core.EventHandlers.ActivityEventHandlers;

public class ProcessTagHandler(IServiceProvider provider) : IEventHandler<ActivityWasCommittedEvent>
{
    private ITimelineRepository _timelineRepository = provider.GetRequiredService<ITimelineRepository>();

    public async Task Handle(ActivityWasCommittedEvent @event, CancellationToken cancellationToken)
    {
        var timeline = new TimelineModel(@event.TagId, @event.EffectedAt, @event.Value);

        await this._timelineRepository.SaveAsync(timeline, cancellationToken);

        // TODO: Add event sourcing to enable reliable rollback
    }

    public void Dispose()
    {
        this._timelineRepository?.Dispose();
        this._timelineRepository = null;
    }
}
