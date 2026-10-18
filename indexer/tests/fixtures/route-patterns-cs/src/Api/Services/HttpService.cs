using System.Net.Http.Json;

namespace Api.Services;

public interface IHttpService
{
    Task<T?> HttpGet<T>(string uri);
}

// The app's own wrapper around HttpClient (eShopOnWeb's BlazorAdmin): the path is the caller's argument.
public class HttpService : IHttpService
{
    private readonly HttpClient _httpClient;
    private readonly string _apiUrl;

    public HttpService(HttpClient httpClient, string apiBase)
    {
        _httpClient = httpClient;
        _apiUrl = apiBase;
    }

    public Task<T?> HttpGet<T>(string uri) => _httpClient.GetFromJsonAsync<T>($"{_apiUrl}{uri}");

    public async Task<bool> HttpDelete(string uri, int id)
    {
        var result = await _httpClient.DeleteAsync($"{_apiUrl}{uri}/{id}");
        return result.IsSuccessStatusCode;
    }

    public Task<HttpResponseMessage> HttpPost(string uri, HttpContent content) => _httpClient.PostAsync(_apiUrl + uri, content);
}
