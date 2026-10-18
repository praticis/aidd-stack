package csv

import "github.com/labstack/echo/v4"

type MigratorWeb struct{}

func (c *MigratorWeb) RegisterRoutes(g *echo.Group) {
	g.GET("/csv/status", c.Status)
	g.PUT("/csv/migrate", c.Migrate)
}

func (c *MigratorWeb) Status(ctx echo.Context) error  { return nil }
func (c *MigratorWeb) Migrate(ctx echo.Context) error { return nil }
