using Acme.Projects.Contracts.Responses.ProjectResponses;

namespace Acme.Projects.Application.Queries;

public interface IProjectQuery
{
    /// <summary>
    /// Asynchronously finds a project by its identifier.
    /// </summary>
    Task<FindProjectByIdResponse?> FindByIdAsync(Guid projectId, CancellationToken cancellationToken = default);
}
