using Acme.Todos.Api.Domain.Models;
using Acme.Shared.Domain.Abstractions;

namespace Acme.Todos.Api.Domain.Interfaces.Repositories;

public interface ITodoRepository : IBaseRepository<TodoModel, Guid>, ITodoReadRepository
{

}
