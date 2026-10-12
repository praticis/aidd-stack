using Acme.Shared.Data.MongoDB;
using Acme.Shared.Data.MongoDB.Options;

namespace Acme.Reports.Core.Infra.Data.Context;

public class ReportsContext(DbContextOptions options) : DbContext(options)
{
}
