package main

import "github.com/gin-gonic/gin"

func main() {
	r := gin.Default()
	r.GET("/", index) // the application itself: GET /

	v1 := r.Group("/v1")
	v1.GET("", listUsers)          // the group root: GET /v1
	v1.GET("users/:id", getUser)   // no leading slash on a group: GET /v1/users/{id}
	v1.POST("/reports", runReport) // as before

	api := r.Group("/api") // a group named like a client is still a group
	api.GET("/health", health)

	registerAdmin(r.Group("/admin"))
	r.Run()
}

// The group arrives as a parameter: its prefix is not known here, so its root is not a route.
func registerAdmin(rg *gin.RouterGroup) {
	rg.GET("", adminIndex)
}

func index(c *gin.Context)      {}
func listUsers(c *gin.Context)  {}
func getUser(c *gin.Context)    {}
func runReport(c *gin.Context)  {}
func adminIndex(c *gin.Context) {}
func health(c *gin.Context)     {}
