using Acme.Projects.Application.Queries;
using Acme.Projects.Contracts.Responses.ProjectResponses;
using Acme.Projects.Domain.Interfaces;
using Acme.Projects.Domain.Models;
using Acme.Projects.Infra.Data.Context;
using Acme.Shared.Bus.Abstractions;
using Acme.Shared.Data.EntityFramework.Repositories;

namespace Acme.Projects.Infra.Data.Repositories;

public class ProjectReadRepository : BaseReadRepository<ProjectModel, Guid>, IProjectReadRepository, IProjectQuery
{
    public ProjectReadRepository(ProjectsContext context, IServiceBus serviceBus)
        : base(context, serviceBus)
    { }

    public bool Exists(string name)
    {
        var query = base.Query()
            .Where(p => p.Name.ToLower() == name.ToLower());

        return query.FirstOrDefault() is not null;
    }

    async Task<FindProjectByIdResponse?> IProjectQuery.FindByIdAsync(Guid projectId, CancellationToken cancellationToken)
    {
        var project = await base.FindByIdAsync(projectId, cancellationToken);

        if (project is null)
            return null;

        return new FindProjectByIdResponse
        {
            ProjectId = project.Id,
            Name = project.Name,
            TodoIds = project.TodoIds,
            IsArchived = project.IsArchived
        };
    }
}
