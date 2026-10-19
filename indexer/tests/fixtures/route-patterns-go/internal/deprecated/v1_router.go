package deprecated

import (
	"net/http"

	"github.com/prometheus/common/route"
)

type V1Router struct{}

func (v *V1Router) Register(r *route.Router) {
	r.Get("/status", v.handle)
	r.Del("/silence/:sid", v.handle)
}

func (v *V1Router) handle(w http.ResponseWriter, req *http.Request) {}
