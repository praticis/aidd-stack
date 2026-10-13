namespace Acme.Todos.Contracts.Requests.ActivityRequests;

public class RegisterActivityRequest
{
    public string Title { get; set; }

    public int Value { get; set; }

    public Guid TagId { get; set; }

    public DateTime? Date { get; set; }
}
