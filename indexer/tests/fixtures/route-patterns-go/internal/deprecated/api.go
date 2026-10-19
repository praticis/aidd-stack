package deprecated

import "github.com/prometheus/common/route"

// A router type of the package, reached through a struct field of a declared type, in another file; the prefix
// comes from `WithPrefix`, prometheus/common/route's.
type API struct {
	v1      *V1Router
	timeout int
}

func New() *API { return &API{v1: &V1Router{}} }

func (api *API) Register(r *route.Router) {
	api.v1.Register(r.WithPrefix("/api/v1"))
}
