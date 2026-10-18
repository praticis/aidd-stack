package api4

import "net/http"

func (api *API) InitUser() {
	api.BaseRoutes.Users.HandleFunc("", createUser).Methods(http.MethodPost)       // POST /api/v4/users
	api.BaseRoutes.Users.HandleFunc("/login", loginUser).Methods(http.MethodPost)  // POST /api/v4/users/login
	api.BaseRoutes.Root.HandleFunc("/.well-known/openid", openID).Methods("GET")   // GET /.well-known/openid
	// a regex with braces, two verbs: GET and HEAD /api/v4/users/{user_id}/image
	api.BaseRoutes.Users.HandleFunc("/{user_id:[a-z0-9]{26}}/image", getImage).Methods(http.MethodGet, http.MethodHead)
	// literal alternatives: POST /api/v4/users/teams/sync and /api/v4/users/channels/sync
	api.BaseRoutes.Users.HandleFunc("/{kind:teams|channels}/sync", syncKind).Methods(http.MethodPost)
}

func getImage(w http.ResponseWriter, r *http.Request) {}
func syncKind(w http.ResponseWriter, r *http.Request) {}

func createUser(w http.ResponseWriter, r *http.Request) {}
func loginUser(w http.ResponseWriter, r *http.Request)  {}
func openID(w http.ResponseWriter, r *http.Request)     {}
