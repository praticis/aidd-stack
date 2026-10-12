using Acme.Shared.Bus.Abstractions;

namespace Acme.Projects.Application.Commands.ProjectCommands;

public class ArchiveProjectCommand(Guid projectId) : Command
{
    public Guid ProjectId { get; } = projectId;
}
