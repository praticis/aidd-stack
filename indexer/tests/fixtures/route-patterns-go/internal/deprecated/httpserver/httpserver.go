package httpserver

import (
	"net/http"

	"github.com/prometheus/common/route"
)

func Register(r *route.Router) {
	r.Get("/-/healthy", healthy)
}

func healthy(w http.ResponseWriter, r *http.Request) {}
