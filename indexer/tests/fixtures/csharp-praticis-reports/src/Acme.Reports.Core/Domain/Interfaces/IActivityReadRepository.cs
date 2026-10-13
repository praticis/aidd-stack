using Acme.Reports.Core.Domain.Models;
using Acme.Shared.Domain.Abstractions;

namespace Acme.Reports.Core.Domain.Interfaces;

public interface IActivityReadRepository : IBaseReadRepository<ActivityModel, Guid>
{
}
