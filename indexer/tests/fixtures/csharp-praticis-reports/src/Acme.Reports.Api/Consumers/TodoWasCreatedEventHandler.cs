using Acme.Reports.Core.Domain.Enums;
using Acme.Reports.Core.Domain.Interfaces;
using Acme.Reports.Core.Domain.Models;
using Acme.Shared.Bus.Abstractions;
using Acme.Todos.Contracts.Events.TodoEvents;

namespace Acme.Reports.Api.Consumers;

public class TodoWasCreatedEventHandler(IServiceProvider provider) : IEventHandler<TodoWasCreatedEvent>
{
    private ITodoRepository _todoRepository = provider.GetRequiredService<ITodoRepository>();

    public async Task Handle(TodoWasCreatedEvent notification, CancellationToken cancellationToken)
    {
        var accObj = notification.Todo;

        var accModel = new TodoModel(accObj.TodoId, accObj.Name, accObj.Progress, (TodoStatus)accObj.Status);

        await this._todoRepository.CreateAsync(accModel, cancellationToken);
    }

    public void Dispose()
    {
        this._todoRepository?.Dispose();
        this._todoRepository = null;
    }
}
