using Acme.Todos.Api.Application.Commands.TodoCommands;
using Acme.Todos.Api.Domain.Interfaces.Repositories;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Todos.Api.Core.CommandHandlers.TodoCommandHandlers;

public class UpdateTodoCommandHandler(IServiceProvider provider) : ICommandHandler<UpdateTodoCommand>
{
    private ITodoRepository _todoRepository = provider.GetRequiredService<ITodoRepository>();
    private INotificationStore _store = provider.GetRequiredService<INotificationStore>();

    public async Task<bool> Handle(UpdateTodoCommand command, CancellationToken cancellationToken)
    {
        var request = command.Request;

        var todo = await this._todoRepository.FindByIdAsync(command.TodoId, cancellationToken);

        todo.ChangeName(request.Name);

        await this._todoRepository.UpdateAsync(todo, cancellationToken);

        return !this._store.HasNotifications();
    }

    public void Dispose()
    {

    }
}
