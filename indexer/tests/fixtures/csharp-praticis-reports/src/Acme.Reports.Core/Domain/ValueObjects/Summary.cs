namespace Acme.Reports.Core.Domain.ValueObjects;

public class Summary(DateTime summaryDay) : Dictionary<Guid, long>
{
    public string Id => this.ToString();

    public DateTime SummaryDay { get; } = summaryDay;

    public long Total => this.Values.Sum();

    public override string ToString()
        => $"summary:{this.SummaryDay:yyyyMMdd}";
}
