namespace Acme.Projects.Infra.Http.Outbound.TodosApi;

public interface ITodosApiClient
{
    Task<TodoDetails?> GetTodoDetailsAsync(Guid todoId, CancellationToken cancellationToken);
}
