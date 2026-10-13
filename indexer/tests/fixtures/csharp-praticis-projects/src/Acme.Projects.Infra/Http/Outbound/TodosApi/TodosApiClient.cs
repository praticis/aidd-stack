using System.Net;
using System.Text.Json;

namespace Acme.Projects.Infra.Http.Outbound.TodosApi;

public class TodosApiClient(HttpClient httpClient) : ITodosApiClient
{
    public async Task<TodoDetails?> GetTodoDetailsAsync(Guid todoId, CancellationToken cancellationToken)
    {
        using var response = await httpClient.GetAsync($"api/todos/{todoId}/details", cancellationToken);

        if (response.StatusCode == HttpStatusCode.NotFound)
            return null;

        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync(cancellationToken);

        return JsonSerializer.Deserialize<TodoDetails>(json);
    }
}
