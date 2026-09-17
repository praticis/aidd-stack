namespace Shop.Api.Controllers;
[ApiController]
[Route("api/[controller]")]
public class RollupsController : ControllerBase
{
    [HttpGet] public Task<IActionResult> GetAsync() => null;
    [HttpPut("{rollupDay}/reset")] public Task<IActionResult> ResetAsync(DateOnly rollupDay) => null;
}
