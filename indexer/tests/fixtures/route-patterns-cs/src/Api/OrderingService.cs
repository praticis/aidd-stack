namespace Api.Clients;

public class OrderingService(HttpClient http)
{
    // the prefix lives in a field (eShop's services); a word constant stands for one whole segment
    private readonly string remoteServiceBaseUrl = "api/ordering/";
    private const string Orders = "orders";

    public Task<string> GetOrder(int id) => http.GetStringAsync($"{remoteServiceBaseUrl}orders/{id}");

    public Task<string> Recent() => http.GetStringAsync($"api/ordering/{Orders}/recent");

    // a generic wrapper: no segment of its own, so the field stays a base
    public Task<string> Raw(string path) => http.GetStringAsync($"{remoteServiceBaseUrl}{path}");

    private const string ApiUrlBase = "api/v1/orders";

    public Task<string> Cancel(int orderId) => http.GetStringAsync($"{ApiUrlBase}/{orderId}");

    // the repo's own URL helper, in a template
    public Task<string> Drafts(string gateway) => http.GetStringAsync($"{UriHelper.CombineUri(gateway, ApiUrlBase, "drafts")}?api-version=1.0");
}
