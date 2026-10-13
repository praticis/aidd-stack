using Acme.Todos.Contracts.Objects;

namespace Acme.Todos.Contracts.Responses.TodoResponses;

public class ListTodoResponse(IEnumerable<TodoObject> todos) : List<TodoObject>(todos);
