package api

import "github.com/gin-gonic/gin"

func GetAlbums(router *gin.RouterGroup) {
	router.GET("/albums", func(c *gin.Context) {})
}

// the verbs in a package variable of another file
func BatchPhotosEdit(router *gin.RouterGroup) {
	router.Match(MethodsPutPost, "/batch/photos/edit", func(c *gin.Context) {})
}
