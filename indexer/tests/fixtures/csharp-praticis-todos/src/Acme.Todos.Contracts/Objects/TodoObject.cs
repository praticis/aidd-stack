using Acme.Todos.Contracts.Enums;

namespace Acme.Todos.Contracts.Objects;

public class TodoObject
{
    public Guid TodoId { get; set; }

    public string Name { get; set; }

    public int Progress { get; set; }

    public TodoStatus Status { get; set; }
}
