using Microsoft.AspNetCore.Mvc;

namespace RoutePatterns.Api.Stores;

// btcpay's UIStoresController: one class in several files, the [Route] on one half.
[Route("stores")]
public partial class StoresController : Controller
{
    [HttpGet("{storeId}")]
    public IActionResult Dashboard(string storeId) => View();
}
