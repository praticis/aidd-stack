using Shop.Api.Queries;

namespace Shop.Api.Infra;

public class AccountReadRepository : BaseReadRepository, IAccountQuery, IAccountReadRepository
{
    async Task<string?> IAccountQuery.FindByIdAsync(Guid id, CancellationToken ct) => await Task.FromResult<string?>(null);
}

public class GroupReadRepository : BaseReadRepository
{
    public string Describe() => "group";
}

public class BaseReadRepository
{
    public Task<int> CountAsync() => Task.FromResult(0);
}
