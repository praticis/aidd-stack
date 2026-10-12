namespace Acme.Projects.Contracts.Requests.ProjectRequests;

public class CreateProjectRequest
{
    public string Name { get; set; }

    public List<Guid> TodoIds { get; set; } = [];
}
