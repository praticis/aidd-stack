using Microsoft.AspNetCore.Mvc;
using RoutePatterns.Api.Routing;

namespace RoutePatterns.Api.Rest;

// Radarr's RestController<T>: an action routed by the project's attribute, taken by controllers two levels down.
public abstract class RestController<TResource> : Controller
{
    [RestGetById]
    public virtual IActionResult GetResourceById(int id) => Ok();
}

public abstract class RestControllerWithSignalR<TResource> : RestController<TResource>
{
}
