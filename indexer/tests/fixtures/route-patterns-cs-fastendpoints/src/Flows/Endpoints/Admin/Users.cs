using FastEndpoints;
using Flows.Abstractions;
using Flows.Groups;

namespace Flows.Endpoints.Admin;

// under a base of the project, in a group
internal class ListUsers : FlowsEndpointWithoutRequest
{
    public override void Configure()
    {
        Get("/users");
        Group<Administration>();
    }

    public override Task HandleAsync(CancellationToken cancellationToken) => Task.CompletedTask;
}

// FastEndpoints' own base, in a sub-group: `Routes` and `Verbs` before the group
internal class ListInvoices : EndpointWithoutRequest
{
    public override void Configure()
    {
        Routes("invoices");
        Verbs(Http.GET);
        Group<Billing>();
    }

    public override Task HandleAsync(CancellationToken cancellationToken) => Task.CompletedTask;
}

internal class RefundInvoice : Endpoint<RefundRequest>
{
    public override void Configure()
    {
        Post("invoices/{invoiceId}/refund");
        Group<Billing>();
    }

    public override Task HandleAsync(RefundRequest request, CancellationToken cancellationToken) => Task.CompletedTask;
}

internal class RefundRequest
{
    public string InvoiceId { get; set; } = "";
}
