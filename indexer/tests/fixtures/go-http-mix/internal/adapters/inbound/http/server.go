package httpapi

import "net/http"

type Server struct{}

func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", s.health)
	mux.HandleFunc("POST /v1/auth/failed-attempt", s.invalidLogin)
	mux.HandleFunc("GET /v1/users/{id}", s.getUser)
	mux.HandleFunc("/legacy/users", s.legacyUsers)
	mux.Handle("GET /metrics", http.HandlerFunc(s.metrics))
	return mux
}

func (s *Server) health(w http.ResponseWriter, r *http.Request)       {}
func (s *Server) invalidLogin(w http.ResponseWriter, r *http.Request) {}
func (s *Server) getUser(w http.ResponseWriter, r *http.Request)      {}
func (s *Server) legacyUsers(w http.ResponseWriter, r *http.Request)  {}
func (s *Server) metrics(w http.ResponseWriter, r *http.Request)      {}
