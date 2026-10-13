using Acme.Shared.Domain.Abstractions.Models;

namespace Acme.Reports.Core.Domain.Models;

public class TimelineModel : BaseModel<long>
{
    public Guid ReferenceId { get; private set; }

    public int EffectiveDay { get; private set; }

    public long Value { get; private set; }

    protected TimelineModel() { }

    public TimelineModel(Guid referenceId, DateTime effectedAt, int value)
    {
        this.EffectiveDay = int.Parse(effectedAt.ToString("yyyyMMdd"));
        this.Id = GenerateId(referenceId, this.EffectiveDay);
        this.ReferenceId = referenceId;
        this.Value = value;
    }

    public static long GenerateId(Guid referenceId, int effectiveDay)
        => (effectiveDay * 10_000_000_000L) + (uint)referenceId.GetHashCode();
}
