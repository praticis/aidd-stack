using Shop.Api.Queries;

namespace Shop.Api.Infra;

public class AccountReadRepository : BaseReadRepository, IAccountQuery, IAccountReadRepository
{
    async Task<string?> IAccountQuery.FindByIdAsync(Guid id, CancellationToken ct) => await Task.FromResult<string?>(null);
}

public class GroupReadRepository : BaseReadRepository
{
    public string Describe() => "group";

    public bool Unowned() => OwnerId.IsNullOrEmpty();                  // an inherited property, not a static type

    public Task<T?> FindAsync<T>(Guid id) => Task.FromResult<T?>(default);

    public void Configure<T>() { }
}

public class BaseReadRepository
{
    public Task<int> CountAsync() => Task.FromResult(0);

    public Guid? OwnerId { get; set; }

    public void Check(List<string> names) => Assert.Contains("a", names);   // a static class: no extension on it
}

public static class Messages
{
    public static string For(string key) => key;
}

public static class InfraExtensions
{
    public static IServiceCollection AddInfra(this IServiceCollection services) => services;

    public static bool IsNullOrEmpty([NotNullWhen(false)] this Guid? id) => id is null || id == Guid.Empty;

    public static IServiceCollection AddReadModels(
        this IServiceCollection services,
        bool cached) => services;

    public static Task<string> GetAsync(this GroupReadRepository groups, string path) => Task.FromResult(path);

    public static Task<T> GetAsync<T>(this GroupReadRepository groups, string path) => Task.FromResult<T>(default!);

    public static bool Contains(this IEnumerable<string> source, string value, StringComparison comparison) => true;

    public static string RemoteIp(this HttpContext context) => "";
}
