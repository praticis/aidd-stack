using Acme.Reports.Core.Application.Commands.SummaryCommands;
using Acme.Reports.Core.Domain.Interfaces;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Reports.Core.Processors.ActivityProcessors.RegisterActivityProcessor;

public class UpdateCacheStep(IServiceProvider provider) : IRegisterActivityProcessor
{
    private ISummaryRepository _summaryRepository = provider.GetRequiredService<ISummaryRepository>();
    private readonly IServiceBus _serviceBus = provider.GetRequiredService<IServiceBus>();

    public async Task ProcessAsync(RegisterActivityTransfer transfer, CancellationToken cancellationToken)
    {
        var summaryDay = transfer.Event.Activity.OccurredAt;

        if (!this._summaryRepository.Exists(summaryDay))
            await this._serviceBus.SendAsync(new InitializeSummaryCommand(summaryDay), cancellationToken);
    }

    public void Dispose()
    {
        this._summaryRepository = null;
    }
}
