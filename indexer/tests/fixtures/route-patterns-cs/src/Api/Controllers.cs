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

[Area("Admin")]
[Route("[area]/Tenants/{tenantId}/[controller]")]
public class MembersController : Controller
{
    [HttpGet("[action]")]
    public IActionResult ListAsync(string tenantId) => View();
}

[Area("Admin")]
public class TenantsController : Controller
{
    [HttpGet]
    [Route("{area}/{controller}/admin")]
    public IActionResult Admin() => View();
}
