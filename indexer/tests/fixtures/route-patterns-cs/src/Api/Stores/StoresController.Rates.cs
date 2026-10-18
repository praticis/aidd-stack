using Microsoft.AspNetCore.Mvc;

namespace RoutePatterns.Api.Stores;

public partial class StoresController
{
    [HttpGet("{storeId}/rates")]
    public IActionResult Rates(string storeId) => View();
}
