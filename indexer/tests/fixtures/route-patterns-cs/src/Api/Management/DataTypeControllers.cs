using Asp.Versioning;
using Microsoft.AspNetCore.Mvc;
using RoutePatterns.Api.Routing;
using RoutePatterns.Core;

namespace RoutePatterns.Api.Management;

// Umbraco: the routing attribute on a base class, its argument another project's constant; each controller declares
// its API version, and an action maps to another one.
[VersionedManagementRoute(Constants.EntityType.DataType)]
public abstract class DataTypeControllerBase : ControllerBase
{
}

[ApiVersion("1.0")]
public class ByKeyDataTypeController : DataTypeControllerBase
{
    [HttpGet("{id:guid}")]
    public IActionResult ByKey(Guid id) => Ok();

    [HttpDelete($"{{{nameof(id)}:guid}}")]                // Umbraco: an interpolated template, the name from nameof
    public IActionResult Delete(Guid id) => Ok();

    [HttpPut("{id:guid}/validate")]
    [MapToApiVersion("1.1")]
    public IActionResult Validate(Guid id) => Ok();
}

// The attribute two levels up: Document → Content → the attribute's base.
[VersionedManagementRoute(Constants.EntityType.Document)]
public abstract class ContentControllerBase : ControllerBase
{
}

public abstract class DocumentControllerBase : ContentControllerBase
{
}

[ApiVersion("1.0")]
public class PublishDocumentController : DocumentControllerBase
{
    [HttpPut("{id:guid}/publish")]
    public IActionResult Publish(Guid id) => Ok();
}
