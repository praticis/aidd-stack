using Acme.Projects.Contracts.Requests.ProjectRequests;
using Acme.Projects.Contracts.Responses.ProjectResponses;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Projects.Application.Commands.ProjectCommands;

public class CreateProjectCommand(CreateProjectRequest request) : Command<CreateProjectResponse?>
{
    public CreateProjectRequest Request { get; } = request;
}
