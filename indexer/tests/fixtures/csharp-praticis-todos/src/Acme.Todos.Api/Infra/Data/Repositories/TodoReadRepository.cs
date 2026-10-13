using Acme.Todos.Api.Application.Queries;
using Acme.Todos.Api.Domain.Interfaces.Repositories;
using Acme.Todos.Api.Domain.Models;
using Acme.Todos.Api.Infra.Data.Context;
using Acme.Todos.Contracts.Enums;
using Acme.Todos.Contracts.Objects;
using Acme.Todos.Contracts.Responses.TodoResponses;
using Acme.Shared.Bus.Abstractions;
using Acme.Shared.Data.MongoDB.Repositories;
using MongoDB.Driver.Linq;

namespace Acme.Todos.Api.Infra.Data.Repositories;

public class TodoReadRepository : BaseReadRepository<TodoModel, Guid>, ITodoReadRepository, ITodoQuery
{
    public TodoReadRepository(TodosContext context, IServiceBus serviceBus)
        : base(context, serviceBus, Collections.TODO)
    { }

    public async Task<ListTodoResponse> ObtainsAllAsync(CancellationToken cancellationToken = default)
    {
        var todos = await base.GetAllAsync(cancellationToken);

        var result = todos.Select(item => new TodoObject()
        {
            TodoId = item.Id,
            Name = item.Name,
            Progress = item.Progress,
            Status = (TodoStatus)item.Status
        });

        return new ListTodoResponse(result.ToList());
    }

    public async Task<TodoModel?> FindByNameAsync(string todoName, CancellationToken cancellationToken = default)
    {
        try
        {
            var query = base.Query()
                .Where(a => a.Name.ToLowerInvariant().Equals(todoName.ToLowerInvariant()));

            var result = await query.FirstOrDefaultAsync(cancellationToken);

            return result;
        }
        catch (Exception e)
        {
            var msg = $"An error occurred while finding {nameof(TodoModel)} by name: {todoName}.";
            await this.ServiceBus.PublishAsync(new SystemError(msg, e), cancellationToken);
        }

        return default;
    }

    public bool Exists(string todoName)
    {
        var query = base.Query()
            .Where(a => a.Name.ToLowerInvariant().Equals(todoName.ToLowerInvariant()));

        return query.FirstOrDefault() is not null;
    }

    public bool NotExists(string todoName) => !this.Exists(todoName);

    async Task<FindTodoByIdResponse?> ITodoQuery.FindByIdAsync(Guid todoId, CancellationToken cancellationToken)
    {
        var todo = await base.FindByIdAsync(todoId, cancellationToken);

        if (todo is null)
            return null;

        return new FindTodoByIdResponse
        {
            TodoId = todo.Id,
            Name = todo.Name,
            Progress = todo.Progress,
            Status = (TodoStatus)todo.Status
        };
    }
}
