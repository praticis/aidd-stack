namespace Acme.Reports.Core.Infra.Http.Outbound.TodosApi;

public interface ITodosApiClient
{
    Task<TodoDetails?> GetTodoDetailsAsync(Guid todoId, CancellationToken cancellationToken);
}
