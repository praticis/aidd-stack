using Acme.Projects.Domain.Interfaces;
using Acme.Projects.Domain.Models;
using Acme.Projects.Infra.Data.Context;
using Acme.Shared.Bus.Abstractions;
using Acme.Shared.Data.EntityFramework.Repositories;

namespace Acme.Projects.Infra.Data.Repositories;

public class ProjectRepository : BaseRepository<ProjectModel, Guid>, IProjectRepository
{
    private readonly IProjectReadRepository _readRepository;

    public ProjectRepository(ProjectsContext context, IServiceBus serviceBus, IProjectReadRepository readRepository)
        : base(context, serviceBus, readRepository)
    {
        _readRepository = readRepository;
    }

    public bool Exists(string name) => this._readRepository.Exists(name);
}
