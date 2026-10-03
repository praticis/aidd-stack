namespace Shop.Api.Queries;

public interface IAccountQuery
{
    Task<string?> FindByIdAsync(Guid id, CancellationToken ct);
}

public interface IAccountReadRepository
{
    // FindByIdAsync comes from a base interface in another package: not declared here on purpose
    Task<int> CountAsync();
}
