package deprecated

import (
	"net/http"
	"strings"

	"github.com/prometheus/common/route"

	"example.com/routepatterns/internal/deprecated/httpserver"
)

// A prefix read from configuration at runtime is not one the routes take (the default has none), here with the
// routes registered by a function of another package that receives the router.
func Serve(prefix string) {
	routePrefix := "/" + strings.Trim(prefix, "/")
	router := route.New()
	if routePrefix != "/" {
		router = router.WithPrefix(routePrefix)
	}
	httpserver.Register(router)
	http.ListenAndServe(":9093", router)
}
