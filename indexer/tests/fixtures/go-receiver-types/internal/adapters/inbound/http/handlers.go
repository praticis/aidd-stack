package httpapi

import (
	"net/http"

	"example.com/svc/internal/app/usecases"
	pw "example.com/svc/internal/domain/password"
)

type Config struct {
	Complete *usecases.Complete
	Policy   pw.Policy
}

// embedded struct: Complete and Policy are promoted fields of Server
type Server struct {
	Config
}

func (s Server) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /v1/password-reset/complete", s.passwordResetComplete)
	return mux
}

// value receiver + field of pointer type from another package
func (s Server) passwordResetComplete(w http.ResponseWriter, r *http.Request) {
	if err := s.Complete.Execute(r.URL.Query().Get("p")); err != nil {
		w.WriteHeader(http.StatusBadRequest)
	}
	_ = s.Policy.Validate("x")
}
