using Microsoft.AspNetCore.Mvc.Routing;

namespace RoutePatterns.Api.Routing;

// Radarr: a routing attribute of the project — IRouteTemplateProvider, the template set in its constructor from a
// property it sets too, the resource defaulting to the class's constant.
public class VersionedApiControllerAttribute : Attribute, IRouteTemplateProvider
{
    public const string CONTROLLER_RESOURCE = "[controller]";

    public VersionedApiControllerAttribute(int version, string resource = CONTROLLER_RESOURCE)
    {
        Version = version;
        Template = $"api/v{Version}/{resource}";
    }

    public string Template { get; }
    public int Version { get; }
    public int? Order => 2;
    public string Name { get; set; }
}

public class V3ApiControllerAttribute : VersionedApiControllerAttribute
{
    public V3ApiControllerAttribute(string resource = "[controller]")
        : base(3, resource)
    {
    }
}
