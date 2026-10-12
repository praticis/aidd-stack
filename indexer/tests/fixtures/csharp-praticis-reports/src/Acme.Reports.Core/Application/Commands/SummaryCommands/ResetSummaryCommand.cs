using Acme.Shared.Bus.Abstractions;

namespace Acme.Reports.Core.Application.Commands.SummaryCommands;

public class ResetSummaryCommand(DateTime summaryDay) : Command
{
    public DateTime SummaryDay { get; } = summaryDay;
}
