package main

import (
	"github.com/gin-gonic/gin"

	"example.com/routepatterns/internal/users"
)

func main() {
	r := gin.Default()
	r.GET("/", index) // the application itself: GET /

	v1 := r.Group("/v1")
	v1.GET("", listUsers)          // the group root: GET /v1
	v1.GET("users/:id", getUser)   // no leading slash on a group: GET /v1/users/{id}
	v1.POST("/reports", runReport) // as before

	api := r.Group("/api") // a group named like a client is still a group
	api.GET("/health", health)

	registerAdmin(r.Group("/manage"))
	users.Register(v1.Group("/users")) // a group handed to another package
	registerUI(r)

	a := r.Group("/v3")
	registerV3(a)
	registerV4(r, r.Group("/v4"))
	r.Run()
}

// vikunja: the parameter is named like main's group; its prefix comes once, from the call (GET /v3/docs, not
// /v3/v3/docs), and a group made from it adds nothing of main's.
func registerV3(a *gin.RouterGroup) {
	n := a.Group("")
	n.GET("/docs", v3Docs)
	a.GET("/info", v3Info)
}

// The same name holding another group: GET /v4/ws, not /v4/v3/ws.
func registerV4(r *gin.Engine, a *gin.RouterGroup) {
	a.GET("/ws", v4Socket)
}

// The group arrives as a parameter: the call in main gives its prefix, so its root is GET /manage.
func registerAdmin(rg *gin.RouterGroup) {
	rg.GET("", adminIndex)
}

// gotify: a "/" group made in a function that gets the application; its root is the application's (HEAD /).
func registerUI(r *gin.Engine) {
	ui := r.Group("/")
	ui.HEAD("/", uiIndex)
}

func uiIndex(c *gin.Context)    {}
func index(c *gin.Context)      {}
func listUsers(c *gin.Context)  {}
func getUser(c *gin.Context)    {}
func runReport(c *gin.Context)  {}
func adminIndex(c *gin.Context) {}
func health(c *gin.Context)     {}
func v3Docs(c *gin.Context)     {}
func v3Info(c *gin.Context)     {}
func v4Socket(c *gin.Context)   {}
