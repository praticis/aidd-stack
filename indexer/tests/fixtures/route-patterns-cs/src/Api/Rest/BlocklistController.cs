using Microsoft.AspNetCore.Mvc;
using RoutePatterns.Api.Routing;

namespace RoutePatterns.Api.Rest;

// Radarr: the class route from [V3ApiController] — api/v3/Blocklist —, actions by Http* and by the project's verbs.
[V3ApiController]
public class BlocklistController : Controller
{
    [HttpGet]
    public IActionResult GetBlocklist() => Ok();

    [HttpGet("movie")]
    public IActionResult GetMovieBlocklist(int movieId) => Ok();

    [RestDeleteById]
    public IActionResult DeleteBlocklist(int id) => Ok();

    [HttpDelete("bulk")]
    [Audit("bulk/delete")]
    public IActionResult Remove() => Ok();

    [Audit("/purge")]
    public IActionResult Purge() => Ok();   // a filter alone routes nothing: the controller's route, any verb
}

// A resource of its own, and the GET {id} its grandparent declares.
[V3ApiController("wanted/missing")]
public class MissingController : RestControllerWithSignalR<object>
{
    [RestPostById]
    public IActionResult Search() => Ok();
}

// Radarr's StaticResourceController: an empty template written out is the root; two routes on one action are two.
public class StaticResourceController : Controller
{
    [HttpPost("")]                                                  // (POST: the fixture's GET / is another one's)
    public IActionResult Index() => Ok();

    [Route("i/{invoiceId}/status/ws")]
    [Route("i/{invoiceId}/{paymentMethodId}/status/ws")]
    public IActionResult Socket(string invoiceId) => Ok();
}

// A filter of the project next to the framework's [Route]: the route is the [Route]'s.
[Route("api/audits")]
[Audit("audits")]
public class AuditsController : Controller
{
    [HttpGet("{id}")]
    public IActionResult Get(string id) => Ok();

    [Microsoft.AspNetCore.Mvc.HttpGet("{searcherName}/query")]     // the attribute by its qualified name (Umbraco)
    public IActionResult Query(string searcherName) => Ok();

    [Route("/login")]                                               // no verb: any (Umbraco's /umbraco/login)
    public IActionResult Login() => Ok();

    [Route("/logout")]
    [Audit("logout")]                                               // the project's attribute routes nothing: still any
    public IActionResult Logout() => Ok();

    [HttpGet("/content/{**path:regex(^(?!api/).*)}")]               // Radarr: a catch-all with a regex constraint
    public IActionResult Content(string path) => Ok();

    [HttpGet("items/{id?}")]                                        // the optional parameter's short form
    public IActionResult Items(int? id) => Ok();
}
