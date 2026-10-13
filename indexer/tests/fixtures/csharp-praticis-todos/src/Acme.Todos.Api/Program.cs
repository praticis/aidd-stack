using Acme.Shared.Interop;

var builder = WebApplication.CreateBuilder(args);

var services = builder.Services;
var config = builder.Configuration;
var env = builder.Environment;

services.AddServices(config, env);

var app = builder.Build();

var appInfo = app.Services.GetService<AppInfo>();

if (!env.IsProduction())
{
    app.MapOpenApi();
}

app.Logger.LogInformation("Starting {ServiceName} {Version}", appInfo?.ServiceName, appInfo?.Version);

app.MapControllers();
app.Run();
