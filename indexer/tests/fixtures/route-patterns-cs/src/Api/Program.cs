var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

app.MapGet("/", Home);                                               // the application itself: GET /
app.MapGet("/items/by/{name:minlength(1)}", GetByName);              // a constraint with arguments
app.MapGet("/items/type/{typeId}/brand/{brandId?}", GetByBrand);     // an optional parameter

var orders = app.MapGroup("api/orders");
orders.MapGet("/", ListOrders);                                      // the group root: GET /api/orders
orders.MapGet("{orderId:int}", GetOrder);                            // no leading slash on a group

app.MapAdmin();
app.Run();

static string Home() => "ok";
static string GetByName(string name) => name;
static string GetByBrand(int typeId, int? brandId) => "ok";
static string ListOrders() => "ok";
static string GetOrder(int orderId) => "ok";

static class AdminEndpoints
{
    // The route builder arrives as a parameter: its "/" is not known to be the application root.
    public static void MapAdmin(this IEndpointRouteBuilder app)
    {
        app.MapGet("/", AdminHome);
    }

    static string AdminHome() => "ok";
}
