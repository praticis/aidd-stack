using System.Text.Json;
using Acme.Reports.Core.Domain.Interfaces;
using Acme.Reports.Core.Domain.ValueObjects;
using Microsoft.Extensions.Caching.Distributed;

namespace Acme.Reports.Core.Infra.Data.Repositories;

public class SummaryRepository(IServiceProvider provider) : ISummaryRepository
{
    private readonly IDistributedCache _cache = provider.GetRequiredService<IDistributedCache>();

    public bool Exists(DateTime summaryDay)
        => this._cache.Get(new Summary(summaryDay).Id) is not null;

    public async Task<bool> InitializeAsync(Summary summary, CancellationToken cancellationToken = default)
    {
        await this._cache.SetStringAsync(summary.Id, JsonSerializer.Serialize(summary), cancellationToken);
        return true;
    }

    public async Task<Summary> LoadAsync(DateTime summaryDay, CancellationToken cancellationToken = default)
    {
        var summary = new Summary(summaryDay);
        var json = await this._cache.GetStringAsync(summary.Id, cancellationToken);

        if (json is null)
            return summary;

        foreach (var entry in JsonSerializer.Deserialize<Dictionary<Guid, long>>(json)!)
            summary[entry.Key] = entry.Value;

        return summary;
    }

    public Task<bool> RemoveAsync(DateTime summaryDay, CancellationToken cancellationToken = default)
    {
        this._cache.Remove(new Summary(summaryDay).Id);
        return Task.FromResult(true);
    }
}
