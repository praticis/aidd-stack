using Acme.Todos.Contracts.Objects;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Todos.Contracts.Events.ActivityEvents;

public class ActivityWasCreatedEvent : Event
{
    public ActivityObject Activity { get; set; }

    public ActivityWasCreatedEvent() : base(ExecutionMode.Enqueue)
    { }

    public ActivityWasCreatedEvent(ActivityObject activity) : base(ExecutionMode.Enqueue)
        => this.Activity = activity;
}
