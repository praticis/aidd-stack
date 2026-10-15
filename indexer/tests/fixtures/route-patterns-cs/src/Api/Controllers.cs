using Microsoft.AspNetCore.Mvc;

namespace Api;

// Conventional routing ({controller}/{action}): a template-less action has no path of its own here.
public class AccountController : Controller
{
    [HttpGet]
    public IActionResult Login() => View();

    [HttpPost]
    public IActionResult Logout() => Ok();
}

[ApiController]
[Route("api/[controller]")]
public class ReportsController : ControllerBase
{
    [HttpGet]
    public IActionResult List() => Ok();

    [HttpGet("{id:int?}")]
    public IActionResult Get(int? id) => Ok();
}
