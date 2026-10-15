using System.Net.Http;
using System.Threading.Tasks;

namespace Api;

public class Listings
{
    private const string ApiUrl = "https://json.example.org/20141201";
    private readonly IHttpClientFactory _factory;

    public Listings(IHttpClientFactory factory) => _factory = factory;

    public async Task Schedules()
    {
        using var options = new HttpRequestMessage(HttpMethod.Post, ApiUrl + "/schedules"); // the path of a base URL constant
        await Request(options);
    }

    public async Task Lineups()
    {
        using var message = new HttpRequestMessage(HttpMethod.Get, ApiUrl + "/lineups/");
        await Request(message);
    }

    // `message` is a parameter here, not the local of Lineups (jellyfin SchedulesDirect.cs).
    private async Task Request(HttpRequestMessage message)
    {
        using var response = await _factory.CreateClient("listings")
            .SendAsync(message);
    }
}
