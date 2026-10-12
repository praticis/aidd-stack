using Acme.Shared.Domain.Abstractions.Models;
// deliberate violation for the fixture: domain must not depend on infra (rule domain-is-pure)
using Acme.Todos.Api.Infra.Data.Context;

namespace Acme.Todos.Api.Domain.Models;

public class ActivityModel : BaseModel
{
    #region Properties

    public Guid TagId { get; private set; }

    public string IdempotencyKey { get; private set; }

    public string Title { get; private set; }

    public int Value { get; private set; }

    public DateTime OccurredAt { get; private set; }

    public DateTime CreatedAt { get; private set; }

    #endregion

    #region Constructors

    public ActivityModel()
    { }

    public ActivityModel(string idempotencyKey, string title, int value, DateTime occurredAt, Guid tagId)
    {
        this.TagId = tagId;
        this.IdempotencyKey = idempotencyKey;
        this.Title = title;
        this.Value = value;
        this.OccurredAt = occurredAt;
        this.CreatedAt = DateTime.UtcNow;
    }

    #endregion
}
