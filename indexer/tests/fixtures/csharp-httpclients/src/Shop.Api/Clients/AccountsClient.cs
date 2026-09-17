namespace Shop.Api.Clients;
public class AccountsClient : IAccountsClient
{
    private readonly HttpClient _httpClient;
    public AccountsClient(HttpClient httpClient) => _httpClient = httpClient;

    public async Task<AccountDetails?> GetDetailsAsync(Guid accountId, CancellationToken ct)
    {
        var response = await _httpClient.GetAsync($"api/accounts/{accountId}/details", ct);
        return await response.Content.ReadFromJsonAsync<AccountDetails>(cancellationToken: ct);
    }
    public Task<AccountDetails?> GetDetails2Async(Guid accountId) =>
        _httpClient.GetFromJsonAsync<AccountDetails>($"api/accounts/{accountId}/details");
    public async Task RegisterAsync(RegisterTransactionRequest request)
    {
        using var msg = new HttpRequestMessage(HttpMethod.Post, "api/transactions") { Content = JsonContent.Create(request) };
        using var res = await _httpClient.SendAsync(msg);
    }
    public async Task ViaFactory(IHttpClientFactory factory, string id)
    {
        var client = factory.CreateClient("transaction");
        var r = await client.GetAsync(new Uri($"api/accounts/{id}/details", UriKind.Relative));
        var uri = $"{_options.BaseUrl}/api/accounts/{id}/details";
        var r2 = await client.GetStringAsync(uri);
        var r3 = await client.PostAsJsonAsync("/api/groups", new { });
        var r4 = await _httpClient.GetAsync(string.Format("api/categories/{0}", id));
        var r5 = await _httpClient.GetAsync(Routes.AccountDetails.Replace("{id}", id));
    }
}
public static class Routes { public const string AccountDetails = "api/accounts/{id}/details"; }
public interface ITransactionApi
{
    [Get("/api/accounts/{accountId}/details")]
    Task<AccountDetails> GetDetails(Guid accountId);
}
public class OtherClients
{
    public async Task Flurl(string baseUrl, string id)
    {
        var a = await baseUrl.AppendPathSegment("api/accounts").AppendPathSegment(id).AppendPathSegment("details").GetJsonAsync<AccountDetails>();
        var b = await "api/groups".PostJsonAsync(new { });
        var c = await _flurl.Request("api/categories").GetAsync();
    }
    public async Task RestSharp(RestClient rc, string id)
    {
        var req = new RestRequest($"api/accounts/{id}/details", Method.Get);
        var res = await rc.ExecuteAsync(req);
    }
}
public interface IGroupsApi
{
    [Post("/api/groups")] Task Create([Body] GroupRequest r);
    [Options("/api/groups")] Task Opts();
    [Multipart] [Put("/api/groups/{id}/logo")] Task Logo(string id, [AliasAs("file")] StreamPart s);
}
