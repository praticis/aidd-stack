namespace Accounts.Notifications;

public interface INotifier
{
    void Notify(string message);
}

public class Notifier : INotifier
{
    public virtual void Notify(string message) { }
}

public class AuditNotifier : Notifier
{
    public override void Notify(string message) => base.Notify(message);
}

public class PlainNotifier : Notifier
{
}

public static class Alerts
{
    public static void Plain(PlainNotifier notifier) => notifier.Notify("plain");
}
