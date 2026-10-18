package server

import (
	"github.com/gin-gonic/gin"

	"example.com/routepatterns/internal/photos/api"
)

// photoprism's APIv1: a router in a package variable that another file of the package assigns, handed to the
// functions of another package that register on it.
var APIv1 *gin.RouterGroup

func registerRoutes(router *gin.Engine) {
	api.GetAlbums(APIv1)
	api.BatchPhotosEdit(APIv1)
}
