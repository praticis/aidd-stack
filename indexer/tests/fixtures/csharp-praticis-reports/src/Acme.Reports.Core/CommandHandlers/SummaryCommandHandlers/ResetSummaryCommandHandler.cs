using Acme.Reports.Core.Application.Commands.SummaryCommands;
using Acme.Reports.Core.Application.Validators.SummaryValidators;
using Acme.Reports.Core.Domain.Interfaces;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Reports.Core.CommandHandlers.SummaryCommandHandlers;

public class ResetSummaryCommandHandler(IServiceProvider provider) : ICommandHandler<ResetSummaryCommand>
{
    private ISummaryRepository _summaryRepository = provider.GetRequiredService<ISummaryRepository>();
    private readonly IServiceBus _serviceBus = provider.GetRequiredService<IServiceBus>();

    public async Task<bool> Handle(ResetSummaryCommand command, CancellationToken cancellationToken)
    {
        var summaryDay = command.SummaryDay;

        if (this._summaryRepository.Exists(summaryDay))
        {
            await this._summaryRepository.RemoveAsync(summaryDay, cancellationToken);
            return true;
        }

        await this._serviceBus.SendAsync(new InitializeSummaryCommand(summaryDay), cancellationToken);

        if (this._summaryRepository.Exists(summaryDay))
            return true;

        var notification = new Warning(code: SummaryValidationErrors.SummaryNotExists.ErrorCode, SummaryValidationErrors.SummaryNotExists.ErrorMessage);
        await this._serviceBus.PublishAsync(notification, cancellationToken);

        return true;
    }

    public void Dispose()
    {
        this._summaryRepository = null;
    }
}
