package http

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

func Routes(h *Handlers) http.Handler {
	r := chi.NewRouter()
	r.Get("/health", h.Health)
	r.Post("/v1/auth/failed-attempt", h.FailedAttempt)
	r.Delete("/v1/users/{id}/sessions", h.RevokeSessions)
	internal := r.Group("/internal")
	internal.Get("/v1/users/{id}", h.GetUser)
	return r
}

type Handlers struct{}

func (h *Handlers) Health(w http.ResponseWriter, r *http.Request)         {}
func (h *Handlers) FailedAttempt(w http.ResponseWriter, r *http.Request)  {}
func (h *Handlers) RevokeSessions(w http.ResponseWriter, r *http.Request) {}
func (h *Handlers) GetUser(w http.ResponseWriter, r *http.Request)        {}
