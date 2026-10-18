package main

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

func main() {
	r := chi.NewRouter()
	r.Route("/articles", func(r chi.Router) { // chi: the closure's router lives under the prefix
		r.With(paginate).Get("/", listArticles) // GET /articles — middleware on the closure's router
		r.Get("/search", searchArticles)       // GET /articles/search
		r.Route("/{articleID}", func(r chi.Router) {
			r.Get("/comments", showArticle) // GET /articles/{articleID}/comments
		})
	})
	r.Group(func(r chi.Router) { // an inline group adds no prefix
		r.Get("/health", health)
	})
	api := chi.NewRouter()
	api.Get("/version", version) // GET /api/version: mounted below
	r.Mount("/api", api)
	http.ListenAndServe(":3333", r)
}

// gitea: registrations on the same router inside a Group closure take its prefix.
func webRoutes(m *Router) {
	m.Group("/user", func() {
		m.Get("/login", login)
		m.Group("/settings", func() {
			m.Post("/avatar/delete", deleteAvatar)
		})
	})
}

func listArticles(w http.ResponseWriter, r *http.Request)   {}
func paginate(next http.Handler) http.Handler                { return next }
func searchArticles(w http.ResponseWriter, r *http.Request) {}
func showArticle(w http.ResponseWriter, r *http.Request)    {}
func health(w http.ResponseWriter, r *http.Request)         {}
func version(w http.ResponseWriter, r *http.Request)        {}
func login(w http.ResponseWriter, r *http.Request)          {}
func deleteAvatar(w http.ResponseWriter, r *http.Request)   {}
