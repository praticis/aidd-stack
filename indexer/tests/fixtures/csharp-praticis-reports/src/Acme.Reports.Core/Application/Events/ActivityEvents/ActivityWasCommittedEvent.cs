using Acme.Shared.Bus.Abstractions;

namespace Acme.Reports.Core.Application.Events.ActivityEvents;

public class ActivityWasCommittedEvent(Guid todoId, Guid tagId, DateTime effectedAt, int value) : Event()
{
    public Guid TodoId { get; } = todoId;

    public Guid TagId { get; } = tagId;

    public DateTime EffectedAt { get; } = effectedAt;

    public int Value { get; } = value;
}
