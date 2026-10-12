using Microsoft.EntityFrameworkCore;

namespace Acme.Projects.Infra.Data.Context;

public class ProjectsContext(DbContextOptions<ProjectsContext> options) : DbContext(options)
{
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(ProjectsContext).Assembly);
    }
}
