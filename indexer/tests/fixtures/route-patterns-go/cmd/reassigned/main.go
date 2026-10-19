package main

import (
	"github.com/gin-gonic/gin"

	"example.com/routepatterns/internal/reassigned/apiv3"
)

func main() {
	e := gin.Default()
	api := e.Group("/api")
	apiv3.Mount(api)
	e.Run(":8080")
}
