package api4

import (
	"github.com/gorilla/mux"

	"example.com/routepatterns/internal/model"
)

type Routes struct {
	Root    *mux.Router
	APIRoot *mux.Router
	Users   *mux.Router
}

type API struct {
	BaseRoutes *Routes
}

// mattermost: the subrouters live in struct fields, and the package's other files register on them.
func Init(root *mux.Router) *API {
	api := &API{BaseRoutes: &Routes{}}
	api.BaseRoutes.Root = root
	api.BaseRoutes.APIRoot = root.PathPrefix(model.APIURLSuffix).Subrouter() // another package's constant: /api/v4
	api.BaseRoutes.Users = api.BaseRoutes.APIRoot.PathPrefix("/users").Subrouter()
	api.InitUser()
	return api
}
