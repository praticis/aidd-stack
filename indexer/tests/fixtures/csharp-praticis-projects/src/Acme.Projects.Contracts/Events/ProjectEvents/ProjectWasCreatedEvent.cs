using Acme.Shared.Bus.Abstractions;

namespace Acme.Projects.Contracts.Events.ProjectEvents;

public class ProjectWasCreatedEvent : Event
{
    public Guid ProjectId { get; set; }

    public string Name { get; set; }

    public List<Guid> TodoIds { get; set; } = [];

    protected ProjectWasCreatedEvent() : base(ExecutionMode.Enqueue) { }

    public ProjectWasCreatedEvent(Guid projectId, string name, List<Guid> todoIds) : base(ExecutionMode.Enqueue)
    {
        this.ProjectId = projectId;
        this.Name = name;
        this.TodoIds = todoIds;
    }
}
