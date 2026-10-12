using Acme.Todos.Contracts.Enums;
using Acme.Todos.Contracts.Objects;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Todos.Contracts.Events.TodoEvents;

public class TodoWasCreatedEvent : Event
{
    public TodoObject Todo { get; set; }

    protected TodoWasCreatedEvent() : base(ExecutionMode.Enqueue) { }

    public TodoWasCreatedEvent(TodoObject todo) : base(ExecutionMode.Enqueue)
        => this.Todo = todo;

    public TodoWasCreatedEvent(Guid todoId, string name, int progress, TodoStatus status) : base(ExecutionMode.Enqueue)
        => this.Todo = new TodoObject { TodoId = todoId, Name = name, Progress = progress, Status = status };
}
