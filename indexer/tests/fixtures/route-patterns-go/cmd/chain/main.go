package main

import (
	"net/http"

	"github.com/gorilla/mux"

	"example.com/routepatterns/internal/addsvc"
)

// gorilla's route builder, path and methods before or after the handler (go-kit's profilesvc), and a gateway that
// mounts another package's handler under the prefix http.StripPrefix removes (go-kit's apigateway).
func main() {
	r := mux.NewRouter()
	r.Methods("POST").Path("/profiles/").HandlerFunc(postProfile)
	r.Methods("GET", "HEAD").Path("/profiles/{id}").HandlerFunc(getProfile)
	r.Path("/profiles/{id}").HandlerFunc(deleteProfile).Methods("DELETE")
	r.PathPrefix("/.well-known/oauth").HandlerFunc(oauthMetadata).Methods("GET") // one endpoint: it has a method
	r.PathPrefix("/static/").Handler(http.FileServer(http.Dir("static")))          // a file tree: no route
	r.PathPrefix("/addsvc").Handler(http.StripPrefix("/addsvc", addsvc.NewHTTPHandler()))
	http.ListenAndServe(":8080", r)
}

func postProfile(w http.ResponseWriter, r *http.Request)   {}
func getProfile(w http.ResponseWriter, r *http.Request)    {}
func deleteProfile(w http.ResponseWriter, r *http.Request) {}
func oauthMetadata(w http.ResponseWriter, r *http.Request) {}
