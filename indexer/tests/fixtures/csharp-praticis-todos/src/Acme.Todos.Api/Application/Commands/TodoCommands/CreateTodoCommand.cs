using Acme.Todos.Contracts.Requests.TodoRequests;
using Acme.Todos.Contracts.Responses.TodoResponses;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Todos.Api.Application.Commands.TodoCommands;

public class CreateTodoCommand(CreateTodoRequest request) : Command<CreateTodoResponse?>
{
    public CreateTodoRequest Request { get; } = request;
}
