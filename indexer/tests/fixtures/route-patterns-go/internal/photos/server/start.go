package server

import (
	"github.com/gin-gonic/gin"

	"example.com/routepatterns/internal/photos/config"
)

func Start(conf *config.Config) {
	router := gin.New()

	// the path goes through a method that returns it, or the site's base path before it (configuration)
	APIv1 = router.Group(conf.BaseUri(config.ApiUri))

	registerRoutes(router)
}
