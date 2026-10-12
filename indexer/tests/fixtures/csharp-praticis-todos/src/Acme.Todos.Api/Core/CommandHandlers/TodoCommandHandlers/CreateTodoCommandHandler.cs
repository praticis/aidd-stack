using Acme.Todos.Api.Application.Commands.TodoCommands;
using Acme.Todos.Api.Domain.Enums;
using Acme.Todos.Api.Domain.Interfaces.Repositories;
using Acme.Todos.Api.Domain.Models;
using Acme.Todos.Contracts.Events.TodoEvents;
using Acme.Todos.Contracts.Responses.TodoResponses;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Todos.Api.Core.CommandHandlers.TodoCommandHandlers;

public class CreateTodoCommandHandler(IServiceProvider provider) : ICommandHandler<CreateTodoCommand, CreateTodoResponse>
{
    private readonly INotificationStore _store = provider.GetRequiredService<INotificationStore>();
    private readonly IServiceBus _serviceBus = provider.GetRequiredService<IServiceBus>();
    private ITodoRepository _todoRepository = provider.GetRequiredService<ITodoRepository>();

    public async Task<CreateTodoResponse?> Handle(CreateTodoCommand command, CancellationToken cancellationToken)
    {
        var request = command.Request;

        var todo = new TodoModel(request.Name, request.Progress, TodoStatus.Active);

        await this._todoRepository.CreateAsync(todo, cancellationToken);

        if (this._store.HasNotifications())
            return default;

        var @event = new TodoWasCreatedEvent(todo.Id, todo.Name, todo.Progress, (Contracts.Enums.TodoStatus)todo.Status);

        await this._serviceBus.PublishAsync(@event, cancellationToken);

        return new CreateTodoResponse
        {
            TodoId = todo.Id,
            Name = todo.Name,
            Status = (Contracts.Enums.TodoStatus)todo.Status
        };
    }

    public void Dispose()
    {
        this._todoRepository?.Dispose();
        this._todoRepository = null;
    }
}
