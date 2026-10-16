using Api.Services;

namespace Api.Items;

public class ItemsClient(IHttpService api, ILogger<ItemsClient> logger)
{
    private readonly HttpService _httpService = new HttpService(new HttpClient(), "https://api.example.test/");

    public Task<Item?> Get(int id) => _httpService.HttpGet<Item>($"catalog-items/{id}");

    public Task<bool> Remove(int id) => _httpService.HttpDelete("catalog-items", id);

    public Task<HttpResponseMessage> Create(HttpContent body) => _httpService.HttpPost("catalog-items", body);

    // through the interface the field is typed by
    public Task<List<Item>?> All() => api.HttpGet<List<Item>>("catalog-items?PageSize=10");

    // a string argument on a method that is no wrapper
    public void Loaded(int id) => logger.LogInformation("catalog-items/{Id} loaded", id);
}
