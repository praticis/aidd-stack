namespace Acme.Todos.Contracts.Requests.TodoRequests;

public class CreateTodoRequest
{
    public string Name { get; set; }

    public int Progress { get; set; }
}
