package addsvc

import "net/http"

// NewHTTPHandler returns the service's routes (go-kit's addtransport): served on its own by cmd/addsvc and mounted
// under /addsvc by the gateway in cmd/chain — both are routes.
func NewHTTPHandler() http.Handler {
	m := http.NewServeMux()
	m.HandleFunc("/sum", sum)
	m.HandleFunc("/concat", concat)
	return m
}

func sum(w http.ResponseWriter, r *http.Request)    {}
func concat(w http.ResponseWriter, r *http.Request) {}
