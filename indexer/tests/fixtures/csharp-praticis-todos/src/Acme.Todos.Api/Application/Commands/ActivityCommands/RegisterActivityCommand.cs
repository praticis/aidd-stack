using Acme.Todos.Contracts.Requests.ActivityRequests;
using Acme.Todos.Contracts.Responses.ActivityResponses;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Todos.Api.Application.Commands.ActivityCommands;

public class RegisterActivityCommand(RegisterActivityRequest request) : Command<RegisterActivityResponse>
{
    public RegisterActivityRequest Request { get; } = request;
}
