using Accounts.Models;
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

    public AccountService(IAccountsDb db, AccountsDb context)
    {
        _db = db;
        _context = context;
    }

    public int Save() => _db.SaveChanges() + _db.SaveChanges();

    public void Track(Account account) { _context.Add(account); _context.Remove(account); }
}
