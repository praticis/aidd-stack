using Asp.Versioning;
using Microsoft.AspNetCore.Mvc;
using RoutePatterns.Api.Routing;
using RoutePatterns.Core;

namespace RoutePatterns.Api.Management;

// No [ApiVersion]: Asp.Versioning maps it to the default version the repo configures (2.0, VersioningSetup.cs).
[VersionedManagementRoute("news-dashboard")]
public class NewsDashboardController : ControllerBase
{
    [HttpGet]
    public IActionResult GetDashboard() => Ok();
}

// The argument a constant of several segments, with more appended.
[ApiVersion("1.0")]
[VersionedManagementRoute(Paths.BackOfficeApi.EndpointTemplate + "/graphics")]
public class BackOfficeGraphicsController : ControllerBase
{
    [HttpGet("logo")]
    public IActionResult Logo() => Ok();
}
