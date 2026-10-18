using FastEndpoints;

namespace Flows.Groups;

// FastEndpoints' endpoint groups: `Group<T>()` puts the group's prefix before the routes declared above it, and a
// `SubGroup<TParent>` its own prefix, then its parent's.
public sealed class Administration : Group
{
    public Administration()
    {
        Configure("admin", ep => ep.Description(x => x.WithTags("administration")));
    }
}

public sealed class Billing : SubGroup<Administration>
{
    public Billing()
    {
        Configure(GroupPrefixes.Billing, ep => { });
    }
}

internal static class GroupPrefixes
{
    public const string Billing = "billing";
}
