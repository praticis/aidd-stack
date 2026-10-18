using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;
using RoutePatterns.Api.Routing;
using RoutePatterns.Core;

namespace RoutePatterns.Api.Portal;

// Umbraco's UmbracoMvcConfigureOptions: the token's value a local holds, a constant trimmed of the characters another
// constant lists. The tenant's comes from configuration, read when the app starts: its token stays as written.
public class PortalMvcOptions : IConfigureOptions<MvcOptions>
{
    private readonly IOptions<TenantSettings> _tenant;

    public PortalMvcOptions(IOptions<TenantSettings> tenant) => _tenant = tenant;

    public void Configure(MvcOptions options)
    {
        var portalPath = Constants.System.DefaultPortalPath.TrimStart(Constants.CharArrays.TildeForwardSlash);
        options.Conventions.Add(new PortalTokenConvention(Constants.Routing.PortalToken, portalPath));
        options.Conventions.Add(new PortalTokenConvention(Constants.Routing.TenantToken, _tenant.Value.Path));
    }
}

public class TenantSettings
{
    public string Path { get; set; } = "";
}
