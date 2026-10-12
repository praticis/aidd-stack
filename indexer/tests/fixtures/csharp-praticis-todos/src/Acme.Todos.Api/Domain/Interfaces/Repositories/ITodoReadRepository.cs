using Acme.Todos.Api.Domain.Models;
using Acme.Shared.Domain.Abstractions;

namespace Acme.Todos.Api.Domain.Interfaces.Repositories;

public interface ITodoReadRepository : IBaseReadRepository<TodoModel, Guid>
{
    /// <summary>
    /// Asynchronously finds a model by name.
    /// </summary>
    Task<TodoModel?> FindByNameAsync(string todoName, CancellationToken cancellationToken = default);

    /// <summary>
    /// Checks if a model exists by its identification todo name.
    /// </summary>
    bool Exists(string todoName);

    /// <summary>
    /// Checks if a model not exists by its identification todo name.
    /// </summary>
    bool NotExists(string todoName);
}
