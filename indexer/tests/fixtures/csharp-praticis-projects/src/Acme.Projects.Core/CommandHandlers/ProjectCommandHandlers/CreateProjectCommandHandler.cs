using Acme.Projects.Application.Commands.ProjectCommands;
using Acme.Projects.Contracts.Events.ProjectEvents;
using Acme.Projects.Contracts.Responses.ProjectResponses;
using Acme.Projects.Domain.Interfaces;
using Acme.Projects.Domain.Models;
using Acme.Projects.Infra.Http.Outbound.TodosApi;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Projects.Core.CommandHandlers.ProjectCommandHandlers;

public class CreateProjectCommandHandler(IServiceProvider provider) : ICommandHandler<CreateProjectCommand, CreateProjectResponse>
{
    private readonly INotificationStore _store = provider.GetRequiredService<INotificationStore>();
    private readonly IServiceBus _serviceBus = provider.GetRequiredService<IServiceBus>();
    private readonly ITodosApiClient _todosApiClient = provider.GetRequiredService<ITodosApiClient>();
    private IProjectRepository _projectRepository = provider.GetRequiredService<IProjectRepository>();

    public async Task<CreateProjectResponse?> Handle(CreateProjectCommand command, CancellationToken cancellationToken)
    {
        var request = command.Request;

        foreach (var todoId in request.TodoIds)
        {
            // Outbound HTTP call to the Todos service: every todo grouped by the project must exist upstream.
            var todoDetails = await this._todosApiClient.GetTodoDetailsAsync(todoId, cancellationToken);

            if (todoDetails is null)
                return default;
        }

        var project = new ProjectModel(request.Name, request.TodoIds);

        await this._projectRepository.CreateAsync(project, cancellationToken);

        if (this._store.HasNotifications())
            return default;

        var @event = new ProjectWasCreatedEvent(project.Id, project.Name, project.TodoIds);

        await this._serviceBus.PublishAsync(@event, cancellationToken);

        return new CreateProjectResponse
        {
            ProjectId = project.Id,
            Name = project.Name,
            TodoCount = project.TodoIds.Count
        };
    }

    public void Dispose()
    {
        this._projectRepository?.Dispose();
        this._projectRepository = null;
    }
}
