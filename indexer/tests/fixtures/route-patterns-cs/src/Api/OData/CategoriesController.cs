using Microsoft.AspNetCore.Mvc;

namespace RoutePatterns.Api.OData;

// OData's conventions for the actions without a template: Post on the entity set (the controller's name), Put / Patch
// / Delete with a `key` on one entity — `Categories({key})`.
public class CategoriesController : WebApiController<Category>
{
    [HttpGet("Categories({key})")]
    public IActionResult Get(int key) => Ok();

    [HttpPost]
    public IActionResult Post([FromBody] Category model) => Ok();

    [HttpPut]
    public IActionResult Put(int key, Category model) => Ok();

    [HttpPatch]
    public IActionResult Patch(int key, Category model) => Ok();

    [HttpDelete]
    public IActionResult Delete(int key) => Ok();
}

// Smartstore's stubs: no key, hidden from the API — the conventions route them nowhere (only the templated GET is a route).
public class DiscountsController : WebApiController<Category>
{
    [HttpGet("Discounts")]
    public IActionResult Get() => Ok();

    [HttpPut, ApiExplorerSettings(IgnoreApi = true)]
    public IActionResult Put() => Forbid();

    [HttpDelete, ApiExplorerSettings(IgnoreApi = true)]
    public IActionResult Delete() => Forbid();
}

// Not OData: the same action names under a plain [Route] keep the controller's route.
[Route("api/shelves")]
public class ShelvesController : ControllerBase
{
    [HttpPut]
    public IActionResult Put(int key) => Ok();
}

public class Category
{
}
