using Microsoft.AspNetCore.Mvc;
using RoutePatterns.Api.Routing;

namespace RoutePatterns.Api.Rest;

// Radarr's ProviderControllerBase: not a controller by its name or its base, but its actions are each derived
// controller's — with RestController's GET {id} two levels further up.
public abstract class ProviderControllerBase<TResource> : RestControllerWithSignalR<TResource>
{
    [HttpGet]
    public IActionResult GetAll() => Ok();

    [HttpPost("test")]
    public IActionResult Test() => Ok();

    [RestPutById]
    public IActionResult UpdateProvider(int id, object resource) => Ok();

    [HttpPut("bulk")]
    public virtual IActionResult UpdateProvider(object bulk) => Ok();
}

[V3ApiController]
public class DownloadClientController : ProviderControllerBase<object>
{
}

// `[NonAction]` on an override takes the inherited action out: GET /api/v3/Calendar only.
[V3ApiController]
public class CalendarController : RestControllerWithSignalR<object>
{
    [NonAction]
    public override IActionResult GetResourceById(int id) => Ok();

    [HttpGet]
    public IActionResult GetCalendar() => Ok();
}

// `[NonAction]` on one overload: the other stays an action (Radarr's MetadataController keeps PUT {id}, not PUT bulk).
[V3ApiController]
public class MetadataController : ProviderControllerBase<object>
{
    [NonAction]
    public override IActionResult UpdateProvider(object bulk) => Ok();
}

// `[NonAction]` in a base between them: no GET {id} for the controllers below (Radarr's ReleaseControllerBase).
public abstract class ReleaseControllerBase : RestController<object>
{
    [NonAction]
    public override IActionResult GetResourceById(int id) => Ok();
}

[V3ApiController]
public class ReleaseController : ReleaseControllerBase
{
    [HttpGet]
    public IActionResult Search() => Ok();
}
