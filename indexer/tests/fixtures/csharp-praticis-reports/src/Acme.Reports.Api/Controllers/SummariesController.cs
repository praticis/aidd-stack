using Acme.Reports.Core.Application.Commands.SummaryCommands;
// deliberate violation for the fixture: controllers dispatch through the bus, never reference handlers (rule controllers-dispatch-through-bus)
using Acme.Reports.Core.CommandHandlers.SummaryCommandHandlers;
using Acme.Reports.Core.Domain.Interfaces;
using Acme.Reports.Contracts.Objects;
using Acme.Shared.Api.Response;
using Microsoft.AspNetCore.Mvc;

namespace Acme.Reports.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class SummariesController(IServiceProvider provider) : InternalControllerBase(provider)
{
    private ISummaryRepository _summaryRepository = provider.GetRequiredService<ISummaryRepository>();

    [HttpGet]
    public async Task<IActionResult> GetAsync(CancellationToken cancellationToken)
    {
        this.PropagateContext();

        var summary = await this._summaryRepository.LoadAsync(DateTime.UtcNow, cancellationToken);

        return await this.ResponseAsync(new SummaryObject { Day = summary.SummaryDay, Total = summary.Total });
    }

    [HttpPut("{summaryDay:datetime}/reset")]
    public async Task<IActionResult> ResetAsync(DateTime summaryDay, CancellationToken cancellationToken)
    {
        this.PropagateContext();

        await this.ServiceBus.SendAsync(new ResetSummaryCommand(summaryDay), cancellationToken);
        var summary = await this._summaryRepository.LoadAsync(summaryDay, cancellationToken);

        return await this.ResponseAsync(new SummaryObject { Day = summary.SummaryDay, Total = summary.Total });
    }
}
