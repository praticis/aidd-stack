using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Filters;

namespace RoutePatterns.Api.Stores;

// Umbraco's BackOfficeLoginController: an action with no routing attribute is the controller's route, any verb. The
// framework's other members are not actions: static, non-public, generic, `Dispose`, an override of its hooks.
[Route(LoginPath)]
public class StoreLoginController : Controller
{
    public const string LoginPath = "/stores/login";

    public StoreLoginController() { }

    public IActionResult Index(string? returnUrl) => View();

    public static string Normalize(string url) => url;

    protected IActionResult Back() => Redirect("/");

    public T Option<T>() => default!;

    public new void Dispose() { }

    public override void OnActionExecuting(ActionExecutingContext context) { }
}
