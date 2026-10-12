using Acme.Projects.Domain.Models;
using Acme.Shared.Domain.Abstractions;

namespace Acme.Projects.Domain.Interfaces;

public interface IProjectReadRepository : IBaseReadRepository<ProjectModel, Guid>
{
    /// <summary>
    /// Checks if a project exists by its name.
    /// </summary>
    bool Exists(string name);
}
