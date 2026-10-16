package apiv1

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

// Routes returns the router cmd/crossfile mounts at /api/v1.
func Routes() chi.Router {
	m := chi.NewRouter()
	m.Get("/version", version) // GET /api/v1/version
	m.Route("/repos/{owner}", func(r chi.Router) {
		r.Get("/", listRepos) // GET /api/v1/repos/{owner}: the closure's router is m
		addIssueRoutes(r)     // a helper fed the closure's router
	})
	addHooks := func(r chi.Router) { // a helper that is a closure, called by its variable's name
		r.Get("/hooks", listHooks)
	}
	m.Route("/orgs/{org}", func(r chi.Router) {
		addHooks(r) // GET /api/v1/orgs/{org}/hooks
	})
	return m
}

// The router arrives as a parameter: the call gives its prefix (GET /api/v1/repos/{owner}/issues).
func addIssueRoutes(r chi.Router) {
	r.Get("/issues", listIssues)
}

func version(w http.ResponseWriter, req *http.Request)    {}
func listRepos(w http.ResponseWriter, req *http.Request)  {}
func listIssues(w http.ResponseWriter, req *http.Request) {}
func listHooks(w http.ResponseWriter, req *http.Request)  {}
