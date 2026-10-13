using Acme.Reports.Core.Domain.Models;
using Acme.Shared.Domain.Abstractions;

namespace Acme.Reports.Core.Domain.Interfaces;

public interface ITodoRepository : IBaseRepository<TodoModel, Guid>, ITodoReadRepository
{
    /// <summary>
    /// Performs an atomic update of the todo progress.
    /// Use positive values for Credits and negative values for Debits.
    /// </summary>
    Task<bool> UpdateProgressAsync(Guid todoId, long amount, CancellationToken cancellationToken = default);
}
