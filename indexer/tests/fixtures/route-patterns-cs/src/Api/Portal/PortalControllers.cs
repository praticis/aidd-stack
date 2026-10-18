using Microsoft.AspNetCore.Mvc;
using RoutePatterns.Api.Routing;

namespace RoutePatterns.Api.Portal;

[PortalRoute("pages")]
public class PagesController : ControllerBase
{
    [HttpGet("{id:int}")]
    public IActionResult Page(int id) => Ok();
}

[TenantRoute("reports")]
public class TenantReportsController : ControllerBase
{
    [HttpGet]
    public IActionResult Summary() => Ok();
}
