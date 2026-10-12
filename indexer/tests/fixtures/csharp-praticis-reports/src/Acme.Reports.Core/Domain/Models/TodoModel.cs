using Acme.Reports.Core.Domain.Enums;
using Acme.Shared.Domain.Abstractions.Models;

namespace Acme.Reports.Core.Domain.Models;

public class TodoModel : BaseModel
{
    public string Name { get; private set; }

    public long Progress { get; private set; }

    public TodoStatus Status { get; private set; }

    public TodoModel(Guid id, string name, long progress, TodoStatus status)
    {
        base.Id = id;
        this.Name = name;
        this.Progress = progress;
        this.Status = status;
    }

    public void Activate() => this.Status = TodoStatus.Active;

    public void Deactivate() => this.Status = TodoStatus.Inactive;
}
