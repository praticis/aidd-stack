var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

// A second app of the repo with a route the API exposes too: one endpoint per project.
app.MapGet("/health", Health);
app.Run();

static string Health() => "ok";
