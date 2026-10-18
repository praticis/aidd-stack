using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Filters;
using Microsoft.AspNetCore.Mvc.Routing;
using RoutePatterns.Core;

namespace RoutePatterns.Api.Routing;

// Radarr: a verb and a template as the project's own attributes — IActionHttpMethodProvider, or a subclass of an
// Http*Attribute with the template handed to its base, or with none.
[AttributeUsage(AttributeTargets.Method)]
public class RestGetByIdAttribute : Attribute, IActionHttpMethodProvider, IRouteTemplateProvider
{
    public IEnumerable<string> HttpMethods => new[] { "GET" };
    public string Template => "{id:int}";
    public int? Order => 0;
    public string Name { get; }
}

public class RestDeleteByIdAttribute : HttpDeleteAttribute
{
    public RestDeleteByIdAttribute()
        : base("{id:int}")
    {
    }
}

public class RestPostByIdAttribute : HttpPostAttribute
{
}

public class RestPutByIdAttribute : HttpPutAttribute
{
    public RestPutByIdAttribute()
        : base("{id:int?}")
    {
    }
}

// Umbraco: a RouteAttribute two levels up — a prefix from another project's constant, Asp.Versioning's segment, and
// the controller's own part with its leading slash trimmed.
public class ManagementRouteAttribute : RouteAttribute
{
    public ManagementRouteAttribute(string template)
        : base(template.TrimStart('/'))
    {
    }
}

public class VersionedManagementRouteAttribute : ManagementRouteAttribute
{
    public VersionedManagementRouteAttribute(string template)
        : base($"{Constants.Web.ManagementApiPath}v{{version:apiVersion}}/{template.TrimStart('/')}")
    {
    }
}

// Not routing: a filter of the project, with an argument that reads like a path.
public class AuditAttribute : ActionFilterAttribute
{
    public AuditAttribute(string category)
    {
        Category = category;
    }

    public string Category { get; }
}
