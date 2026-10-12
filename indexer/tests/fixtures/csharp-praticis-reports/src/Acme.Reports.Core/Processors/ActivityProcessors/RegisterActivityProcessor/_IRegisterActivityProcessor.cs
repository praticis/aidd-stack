namespace Acme.Reports.Core.Processors.ActivityProcessors.RegisterActivityProcessor;

public interface IRegisterActivityProcessor : IDisposable
{
    Task ProcessAsync(RegisterActivityTransfer transfer, CancellationToken cancellationToken);
}
