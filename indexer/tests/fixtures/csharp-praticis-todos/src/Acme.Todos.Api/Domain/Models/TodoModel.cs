using Acme.Todos.Api.Domain.Enums;
using Acme.Shared.Domain.Abstractions.Models;

namespace Acme.Todos.Api.Domain.Models;

public class TodoModel : BaseModel
{
    public string Name { get; private set; }

    public int Progress { get; private set; }

    public TodoStatus Status { get; private set; }

    public TodoModel() : base()
    { }

    public TodoModel(string name, int progress, TodoStatus status)
    {
        this.Name = name;
        this.Progress = progress;
        this.Status = status;
    }

    public void ChangeName(string newName) => this.Name = newName;

    public void Activate() => this.Status = TodoStatus.Active;

    public void Deactivate() => this.Status = TodoStatus.Inactive;
}
