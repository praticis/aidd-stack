using Accounts.Models;
using Accounts.Dto;
using Accounts.Services;
using Microsoft.AspNetCore.Mvc;

namespace Accounts.Api;

[ApiController]
[Route("api/[controller]")]
public class AccountsController : ControllerBase
{
    private readonly AccountService _service;

    public AccountsController(AccountService service) => _service = service;

    [HttpGet("{id}/details")]
    public IActionResult Details(string id)
    {
        _service.MarkSeen(id);
        return Ok(id);
    }
}
