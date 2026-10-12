using Acme.Projects.Domain.Models;
using Acme.Shared.Domain.Abstractions;

namespace Acme.Projects.Domain.Interfaces;

public interface IProjectRepository : IBaseRepository<ProjectModel, Guid>, IProjectReadRepository
{

}
