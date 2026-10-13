namespace Acme.Todos.Contracts.Responses.ActivityResponses;

public class RegisterActivityResponse
{
    public Guid ActivityId { get; set; }

    public string IdempotencyKey { get; set; }

    public string Title { get; set; }

    public int Value { get; set; }

    public Guid TagId { get; set; }

    public DateTime CreatedAt { get; set; }
}
