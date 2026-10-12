using Acme.Todos.Contracts.Responses.TodoResponses;

namespace Acme.Todos.Api.Application.Queries;

public interface ITodoQuery
{
    /// <summary>
    /// Retrieves all todos.
    /// </summary>
    Task<ListTodoResponse> ObtainsAllAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Asynchronously finds an todo by its identifier.
    /// </summary>
    Task<FindTodoByIdResponse?> FindByIdAsync(Guid todoId, CancellationToken cancellationToken = default);
}
