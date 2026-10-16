using Microsoft.AspNetCore.Mvc;

namespace Api;

// The route every controller deriving from it inherits when it declares none of its own.
[ApiController]
[Route("[controller]")]
public class BaseApiController : ControllerBase
{
}
