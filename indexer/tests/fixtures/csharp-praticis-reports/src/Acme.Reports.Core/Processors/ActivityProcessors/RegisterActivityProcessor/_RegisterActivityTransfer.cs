using Acme.Todos.Contracts.Events.ActivityEvents;

namespace Acme.Reports.Core.Processors.ActivityProcessors.RegisterActivityProcessor;

public class RegisterActivityTransfer(ActivityWasCreatedEvent @event)
{
    public ActivityWasCreatedEvent Event { get; } = @event;
}
