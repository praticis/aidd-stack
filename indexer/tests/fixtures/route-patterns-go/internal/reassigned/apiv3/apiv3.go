package apiv3

import "github.com/gin-gonic/gin"

// A router parameter reassigned to a group of itself: the group's prefix comes after the one the caller's router has.
func Mount(r *gin.RouterGroup) {
	r = r.Group("/v3")
	r.GET("/ping", ping)
}

func ping(c *gin.Context) {}
