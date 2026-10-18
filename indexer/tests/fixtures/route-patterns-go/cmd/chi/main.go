package main

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

func main() {
	r := chi.NewRouter()
	r.Post("/", submit)                            // the root router, built in main: POST /
	r.Get("/articles/{slug:[a-z-]+}", getArticle) // a regex constraint: GET /articles/{slug}
	r.Mount("/admin", adminRouter())
	http.ListenAndServe(":3333", r)
}

// A router built and returned by a function: its "/" is where main mounts it (GET /admin).
func adminRouter() chi.Router {
	r := chi.NewRouter()
	r.Get("/", adminHome)
	return r
}

func submit(w http.ResponseWriter, req *http.Request)     {}
func getArticle(w http.ResponseWriter, req *http.Request) {}
func adminHome(w http.ResponseWriter, req *http.Request)  {}
