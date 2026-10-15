namespace Api;

public class CatalogClient(HttpClient http, string baseUrl)
{
    // a literal query string does not make the template invalid
    public Task<string> GetItem(int id) => http.GetStringAsync($"{baseUrl}items/{id}?api-version=2.0");

    // a nested generic argument is still the same client method
    public Task<List<string>?> ListBrands() => http.GetFromJsonAsync<List<string>>("api/catalog/brands");
}
