using Acme.Reports.Core.Domain.ValueObjects;

namespace Acme.Reports.Core.Domain.Interfaces;

public interface ISummaryRepository
{
    bool Exists(DateTime summaryDay);

    Task<bool> InitializeAsync(Summary summary, CancellationToken cancellationToken = default);

    Task<Summary> LoadAsync(DateTime summaryDay, CancellationToken cancellationToken = default);

    Task<bool> RemoveAsync(DateTime summaryDay, CancellationToken cancellationToken = default);
}
