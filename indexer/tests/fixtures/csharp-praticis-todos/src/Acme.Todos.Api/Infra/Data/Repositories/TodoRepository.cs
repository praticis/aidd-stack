using Acme.Todos.Api.Domain.Interfaces.Repositories;
using Acme.Todos.Api.Domain.Models;
using Acme.Todos.Api.Infra.Data.Context;
using Acme.Shared.Bus.Abstractions;
using Acme.Shared.Data.MongoDB.Repositories;

namespace Acme.Todos.Api.Infra.Data.Repositories;

public class TodoRepository : BaseRepository<TodoModel, Guid>, ITodoRepository
{
    private readonly ITodoReadRepository _readRepository;

    public TodoRepository(TodosContext context, IServiceBus serviceBus, ITodoReadRepository readRepository)
        : base(context, serviceBus, readRepository, Collections.TODO)
    {
        _readRepository = readRepository;
    }

    public Task<TodoModel?> FindByNameAsync(string todoName, CancellationToken cancellationToken = default)
        => this._readRepository.FindByNameAsync(todoName, cancellationToken);

    public bool Exists(string todoName) => this._readRepository.Exists(todoName);

    public bool NotExists(string todoName) => this._readRepository.NotExists(todoName);
}
