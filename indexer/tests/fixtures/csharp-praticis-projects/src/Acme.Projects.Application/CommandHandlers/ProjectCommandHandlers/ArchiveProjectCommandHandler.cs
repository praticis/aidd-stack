using Acme.Projects.Application.Commands.ProjectCommands;
using Acme.Projects.Domain.Interfaces;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Projects.Application.CommandHandlers.ProjectCommandHandlers;

// deliberate violation for the fixture: handlers live in .Core (rule elements-live-in-their-layer)
public class ArchiveProjectCommandHandler(IServiceProvider provider) : ICommandHandler<ArchiveProjectCommand>
{
    private readonly IProjectRepository _projectRepository = provider.GetRequiredService<IProjectRepository>();
    private readonly INotificationStore _store = provider.GetRequiredService<INotificationStore>();

    public async Task<bool> Handle(ArchiveProjectCommand command, CancellationToken cancellationToken)
    {
        var project = await this._projectRepository.FindByIdAsync(command.ProjectId, cancellationToken);

        if (project is null)
            return false;

        project.Archive();

        await this._projectRepository.UpdateAsync(project, cancellationToken);

        return !this._store.HasNotifications();
    }

    public void Dispose()
    {

    }
}
