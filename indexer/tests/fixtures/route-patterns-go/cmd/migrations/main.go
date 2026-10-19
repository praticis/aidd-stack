package main

import (
	"github.com/labstack/echo/v4"

	"example.com/routepatterns/internal/migration/csv"
)

// A router handed to the method of a value whose type the composite literal writes, from another package.
func main() {
	e := echo.New()
	m := e.Group("/api/v1/migration")
	csvMigrator := &csv.MigratorWeb{}
	csvMigrator.RegisterRoutes(m)
	e.Start(":8080")
}
