using Acme.Shared.Domain.Abstractions.Models;

namespace Acme.Reports.Core.Domain.Models;

public class ActivityModel : BaseModel
{
    public Guid TagId { get; private set; }

    public string Title { get; private set; }

    public int Value { get; private set; }

    public DateTime SettledAt { get; private set; }

    public DateTime? CommittedAt { get; private set; }

    public DateTime? RolledBackAt { get; private set; }

    protected ActivityModel() { }

    public ActivityModel(Guid activityId, Guid tagId, string title, int value, DateTime settledAt)
    {
        this.Id = activityId;
        this.TagId = tagId;
        this.Title = title;
        this.Value = value;
        this.SettledAt = settledAt;
    }

    public void Commit() => this.CommittedAt = DateTime.UtcNow;

    public void Rollback() => this.RolledBackAt = DateTime.UtcNow;
}
