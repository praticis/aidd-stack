namespace Acme.Reports.Core.Infra.Http.Outbound.TodosApi;

/// <summary>
/// Local subset of the todo exposed by the Activity service. Kept inside Reports on purpose:
/// it is the contract of an outbound HTTP call, not a type shared through a package.
/// </summary>
public class TodoDetails
{
    public Guid TodoId { get; set; }

    public string Name { get; set; }

    public int Progress { get; set; }

    public string Status { get; set; }
}
