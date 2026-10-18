package main

import (
	"net/http"

	"github.com/go-chi/chi/v5"

	apiv1 "example.com/routepatterns/internal/apiv1"
)

// Routers built in other files and packages, mounted here (gitea's routers/init.go, chi's todos-resource).
func main() {
	r := chi.NewRouter()
	r.Mount("/api/v1", apiv1.Routes())          // the router another package returns: its routes under /api/v1
	r.Mount("/todos", todosResource{}.Routes()) // a method of a value built in place, in another file
	http.ListenAndServe(":3333", r)
}
