using Acme.Todos.Contracts.Requests.TodoRequests;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Todos.Api.Application.Commands.TodoCommands;

public class UpdateTodoCommand(Guid todoId, UpdateTodoRequest request) : Command
{
    public Guid TodoId { get; } = todoId;

    public UpdateTodoRequest Request { get; } = request;
}
