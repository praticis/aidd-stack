namespace RoutePatterns.Core;

// Constants another project's routing attribute names by their qualified name (Umbraco Constants-Web.cs).
public static partial class Constants
{
    public static class Web
    {
        public const string ManagementApiPath = "/management/api/";
    }

    public static class EntityType
    {
        public const string DataType = "data-type";
        public const string Document = "document";
    }
}

// A route part of several segments, read only where a routing attribute puts it (Umbraco Paths.cs).
public static class Paths
{
    public static class BackOfficeApi
    {
        public const string EndpointTemplate = "security/back-office";
    }

    public static class MemberApi
    {
        public const string EndpointTemplate = "security/member";
    }
}
