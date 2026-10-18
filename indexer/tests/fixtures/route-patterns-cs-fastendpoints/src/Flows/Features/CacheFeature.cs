namespace Flows.Features;

// Not an endpoint: a `Configure()` override with a `Get(..)` in a class whose bases never reach FastEndpoints'.
public abstract class FeatureBase
{
    public virtual void Configure() { }
    protected void Get(string key) { }
}

public class CacheFeature : FeatureBase
{
    public override void Configure()
    {
        Get("/cache-entries");
    }
}
