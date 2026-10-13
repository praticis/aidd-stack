namespace Acme.Projects.Contracts.Responses.ProjectResponses;

public class FindProjectByIdResponse
{
    public Guid ProjectId { get; set; }

    public string Name { get; set; }

    public List<Guid> TodoIds { get; set; } = [];

    public bool IsArchived { get; set; }
}
