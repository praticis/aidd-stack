using Acme.Reports.Core.Application.Commands.SummaryCommands;
using Acme.Reports.Core.Domain.Interfaces;
using Acme.Reports.Core.Domain.ValueObjects;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Reports.Core.CommandHandlers.SummaryCommandHandlers;

public class InitializeSummaryCommandHandler(IServiceProvider provider) : ICommandHandler<InitializeSummaryCommand>
{
    private ISummaryRepository _summaryRepository = provider.GetRequiredService<ISummaryRepository>();
    private readonly INotificationStore _store = provider.GetRequiredService<INotificationStore>();

    public async Task<bool> Handle(InitializeSummaryCommand command, CancellationToken cancellationToken)
    {
        if (this._summaryRepository.Exists(command.SummaryDay))
            return true;

        var summary = new Summary(command.SummaryDay);

        await this._summaryRepository.InitializeAsync(summary, cancellationToken);

        return !this._store.HasNotifications();
    }

    public void Dispose()
    {
        this._summaryRepository = null;
    }
}
