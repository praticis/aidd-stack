using Acme.Shared.Domain.Abstractions.Models;

namespace Acme.Projects.Domain.Models;

public class ProjectModel : BaseModel
{
    public string Name { get; private set; }

    public List<Guid> TodoIds { get; private set; } = [];

    public bool IsArchived { get; private set; }

    public ProjectModel() : base()
    { }

    public ProjectModel(string name, List<Guid> todoIds)
    {
        this.Name = name;
        this.TodoIds = todoIds;
        this.IsArchived = false;
    }

    public void Archive() => this.IsArchived = true;
}
