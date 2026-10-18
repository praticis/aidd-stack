package main

import "github.com/labstack/echo/v4"

// echo joins a group's prefix and the path as written (`g.prefix + path`): u.GET("s") is GET /users (vikunja), where
// gin and fiber would put a slash between them.
func main() {
	e := echo.New()
	u := e.Group("/user")
	u.GET("s", listAccounts)
	u.GET("/profile", showProfile)
	e.Start(":8080")
}

func listAccounts(c echo.Context) error { return nil }
func showProfile(c echo.Context) error  { return nil }
