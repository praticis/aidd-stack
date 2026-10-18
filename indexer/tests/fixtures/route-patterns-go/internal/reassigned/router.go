package reassigned

import (
	"net/http"

	"github.com/prometheus/common/route"

	"example.com/routepatterns/internal/reassigned/health"
)

// A router reassigned under its own name with a prefix, and returned: its routes, here and in the package that
// receives it, take the prefix though no file mounts the router.
func NewRouter() *route.Router {
	router := route.New()
	router = router.WithPrefix("/api/v2")
	health.Register(router)
	router.Get("/status", status)
	return router
}

func status(w http.ResponseWriter, r *http.Request) {}
