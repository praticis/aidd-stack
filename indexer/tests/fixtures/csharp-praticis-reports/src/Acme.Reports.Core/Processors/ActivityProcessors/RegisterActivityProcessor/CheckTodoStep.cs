using Acme.Reports.Core.Domain.Interfaces;
using Acme.Reports.Core.Infra.Http.Outbound.TodosApi;
using Microsoft.Extensions.Logging;

namespace Acme.Reports.Core.Processors.ActivityProcessors.RegisterActivityProcessor;

public class CheckTodoStep(IServiceProvider provider, IRegisterActivityProcessor processor) : IRegisterActivityProcessor
{
    private ITodoRepository _todoRepository = provider.GetRequiredService<ITodoRepository>();
    private readonly ITodosApiClient _todosApiClient = provider.GetRequiredService<ITodosApiClient>();
    private readonly ILogger<CheckTodoStep> _logger = provider.GetRequiredService<ILogger<CheckTodoStep>>();

    public async Task ProcessAsync(RegisterActivityTransfer transfer, CancellationToken cancellationToken)
    {
        var todoId = transfer.Event.Activity.TodoId;

        if (!this._todoRepository.Exists(todoId))
        {
            // TODO: Fallback and notification
            return;
        }

        // Outbound HTTP call to the Activity service: confirms the todo still exists upstream.
        var todoDetails = await this._todosApiClient.GetTodoDetailsAsync(todoId, cancellationToken);

        if (todoDetails is null)
            this._logger.LogWarning("Todo {TodoId} not found upstream; proceeding with local snapshot", todoId);

        await processor.ProcessAsync(transfer, cancellationToken);
    }

    public void Dispose()
    {
        this._todoRepository?.Dispose();
        this._todoRepository = null;
    }
}
