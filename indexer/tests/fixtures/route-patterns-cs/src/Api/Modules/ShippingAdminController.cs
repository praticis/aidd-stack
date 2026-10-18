using Microsoft.AspNetCore.Mvc;

namespace RoutePatterns.Api.Modules;

// Smartstore's module controllers: the `[Area]` on the base class — inherited, as the framework reads it.
[Area("Admin")]
public abstract class ModuleAdminController : Controller
{
}

[Route("[area]/shipping/{action=index}/{id?}")]
public class ShippingAdminController : ModuleAdminController
{
    public IActionResult Configure() => View();

    [HttpPost]
    public IActionResult Save() => Ok();
}
