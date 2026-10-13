namespace Acme.Todos.Contracts.Objects;

public class ActivityObject
{
    public Guid ActivityId { get; set; }

    public Guid TagId { get; set; }

    public string IdempotencyKey { get; set; }

    public string Title { get; set; }

    public int Value { get; set; }

    public DateTime OccurredAt { get; set; }

    public DateTime CreatedAt { get; set; }
}
