using Flows.Extensions;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();
var routePrefix = builder.Configuration["Flows:RoutePrefix"];   // a deployment's choice: not read
app.MapFlowsApi(routePrefix);

// Code the C# grammar cannot read (in Elsa's workbench Program.cs, valid code it gets lost in; here an `#if` without
// its `#endif`): the parser folds these lines into the receiver of the `MapGet` below, whose evidence is still the
// line `MapGet` is written on.
app.UseFlowsDiagnostics(diagnostics =>
{
    if (useSqlServer)
        diagnostics.UseSqlServer();
#if !NET9_0
    else if (useMySql)
        diagnostics.UseMySql();
    else
        diagnostics.UseSqlite(sp => sp.GetSqliteConnectionString());
});

app.MapGet("/__probe/routes", (IEnumerable<EndpointDataSource> sources) =>
    Results.Json(sources.Count()));
app.Run();
