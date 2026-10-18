package users

import "github.com/gin-gonic/gin"

// gin-realworld: the group comes from cmd/api, users.Register(v1.Group("/users")).
func Register(router *gin.RouterGroup) {
	router.POST("", signUp)          // POST /v1/users
	router.POST("/login", signIn)    // POST /v1/users/login
	me := router.Group("/me").Use(auth) // a group with middleware is still the group
	me.GET("/profile", profile)          // GET /v1/users/me/profile
}

func auth(c *gin.Context)    {}
func profile(c *gin.Context) {}

func signUp(c *gin.Context) {}
func signIn(c *gin.Context) {}
