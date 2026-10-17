package testhelpers

import "net/http"

// A fake courier the tests start (kratos courier/template/testhelpers): test code, no route.
func NewFakeCourier() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /mail", receiveMail)
	return mux
}

func receiveMail(w http.ResponseWriter, r *http.Request) {}
