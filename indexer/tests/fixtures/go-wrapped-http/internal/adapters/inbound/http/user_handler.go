package httpapi

import "net/http"

type ServerConfig struct{}

type Option func(http.Handler) http.Handler

func WithAuthenticate() Option { return func(h http.Handler) http.Handler { return h } }
func WithEnrichUser() Option   { return func(h http.Handler) http.Handler { return h } }

func (sc *ServerConfig) setHandlerSecurity(h http.HandlerFunc, opts ...Option) http.Handler {
	var out http.Handler = h
	for _, o := range opts {
		out = o(out)
	}
	return out
}

type UserHandler struct {
	sc *ServerConfig
}

func (h *UserHandler) registerRoutes(sc *ServerConfig, mux *http.ServeMux) {
	h.sc = sc
	mux.Handle("GET /v1/users/me", sc.setHandlerSecurity(
		h.getUserMe,
		WithAuthenticate(),
		WithEnrichUser(),
	))
	mux.Handle("POST /v1/users", http.HandlerFunc(h.createUser))
	mux.Handle("GET /v1/users/{id}", chain(WithAuthenticate(), WithEnrichUser())(http.HandlerFunc(h.getUser)))
	mux.HandleFunc("GET /v1/password-policy", h.passwordPolicy)
}

func chain(opts ...Option) Option {
	return func(h http.Handler) http.Handler { return h }
}

func (h *UserHandler) getUserMe(w http.ResponseWriter, r *http.Request)      {}
func (h *UserHandler) createUser(w http.ResponseWriter, r *http.Request)     {}
func (h *UserHandler) getUser(w http.ResponseWriter, r *http.Request)        {}
func (h *UserHandler) passwordPolicy(w http.ResponseWriter, r *http.Request) {}
