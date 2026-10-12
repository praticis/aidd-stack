using Acme.Reports.Core.Domain.Models;
using Acme.Shared.Domain.Abstractions;

namespace Acme.Reports.Core.Domain.Interfaces;

public interface ITodoReadRepository : IBaseReadRepository<TodoModel, Guid>
{
}
