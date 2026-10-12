using Acme.Todos.Contracts.Enums;

namespace Acme.Todos.Contracts.Responses.TodoResponses;

public class CreateTodoResponse
{
    public Guid TodoId { get; set; }

    public string Name { get; set; }

    public TodoStatus Status { get; set; }
}
