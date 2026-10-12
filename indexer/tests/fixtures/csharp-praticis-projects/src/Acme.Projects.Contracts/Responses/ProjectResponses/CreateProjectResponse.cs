namespace Acme.Projects.Contracts.Responses.ProjectResponses;

public class CreateProjectResponse
{
    public Guid ProjectId { get; set; }

    public string Name { get; set; }

    public int TodoCount { get; set; }
}
