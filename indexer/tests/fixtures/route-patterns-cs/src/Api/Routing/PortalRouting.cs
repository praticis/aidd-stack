using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.ApplicationModels;
using RoutePatterns.Core;

namespace RoutePatterns.Api.Routing;

// Umbraco's UmbracoBackofficeToken: a convention of the project that writes a value over a token of its own in every
// attribute route — the value given where it is registered (PortalMvcOptions).
public class PortalTokenConvention : IApplicationModelConvention
{
    private readonly string _token;
    private readonly string _value;

    public PortalTokenConvention(string tokenName, string value)
    {
        _token = $"[{tokenName}]";
        _value = value;
    }

    public void Apply(ApplicationModel application)
    {
        foreach (var selector in application.Controllers.SelectMany(c => c.Selectors).Where(s => s.AttributeRouteModel is not null))
        {
            selector.AttributeRouteModel!.Template = selector.AttributeRouteModel.Template?.Replace(_token, _value);
        }
    }
}

// Umbraco's BackOfficeRouteAttribute: the route under the token, `[portalRoot]/` + the template.
public class PortalRouteAttribute : RouteAttribute
{
    public PortalRouteAttribute(string template)
        : base($"[{Constants.Routing.PortalToken}]/" + template.TrimStart('/'))
    {
    }
}

public class TenantRouteAttribute : RouteAttribute
{
    public TenantRouteAttribute(string template)
        : base($"[{Constants.Routing.TenantToken}]/" + template.TrimStart('/'))
    {
    }
}
