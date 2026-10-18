using Asp.Versioning;

namespace RoutePatterns.Api.Management;

public static class VersioningSetup
{
    public static void Configure(ApiVersioningOptions options)
    {
        options.DefaultApiVersion = new ApiVersion(2, 0);
    }
}
