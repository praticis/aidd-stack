using Accounts.Models;
using Accounts.Dto;
using Microsoft.AspNetCore.Mvc;

namespace Accounts.Api;

[ApiController]
[Route("api/[controller]")]
public class AccountsController : ControllerBase
{
    [HttpGet("{id}/details")]
    public IActionResult Details(string id) => Ok(id);
}
