using Microsoft.AspNetCore.Mvc;

namespace Api;

// No [Route] here: BaseApiController's (another file) applies, one level up.
public class DevicesController : BaseApiController
{
    [HttpGet]
    public IActionResult GetDevices() => Ok();

    [HttpGet("Info")]
    public IActionResult GetDeviceInfo() => Ok();

    [HttpPost("Options")]
    public IActionResult UpdateOptions() => Ok();

    [HttpGet("/health")]
    public IActionResult Health() => Ok();
}

// Two classes named SharedBase (Legacy.cs, Admin.cs): which one this derives from is unknown, so nothing is inherited
// and the template-less action is not a route.
public class WidgetsController : SharedBase
{
    [HttpGet]
    public IActionResult All() => Ok();

    [HttpGet("widgets/{id}")]
    public IActionResult One(int id) => Ok();
}
