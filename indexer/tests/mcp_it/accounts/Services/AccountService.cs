using Accounts.Models;
using Accounts.Notifications;
using Microsoft.EntityFrameworkCore;

namespace Accounts.Services;

public interface IAccountsDb
{
    int SaveChanges();
}

public class AccountsDb : DbContext, IAccountsDb
{
}

public class AccountService
{
    private readonly IAccountsDb _db;
    private readonly AccountsDb _context;
    private readonly INotifier _notifier;

    public AccountService(IAccountsDb db, AccountsDb context, INotifier notifier)
    {
        _db = db;
        _context = context;
        _notifier = notifier;
    }

    public int Save() => _db.SaveChanges() + _db.SaveChanges();

    public void Track(Account account) { _context.Add(account); _context.Remove(account); }

    public void MarkSeen(string id) => _notifier.Notify(id);
}
