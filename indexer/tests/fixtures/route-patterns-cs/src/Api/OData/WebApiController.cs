using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.OData.Routing.Controllers;
using Microsoft.AspNetCore.OData.Routing.Attributes;

namespace RoutePatterns.Api.OData;

// Smartstore: the OData route component on the project's base, two levels over ODataController.
public abstract class SmartODataController<TEntity> : ODataController
{
}

[ODataRouteComponent("odata/v1")]
[Route("odata/v1")]
public abstract class WebApiController<TEntity> : SmartODataController<TEntity>
{
}
