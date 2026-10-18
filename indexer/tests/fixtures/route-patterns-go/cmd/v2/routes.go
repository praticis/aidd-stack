package main

// Route constants built from other constants (kratos identity/handler.go).
const (
	RouteCollection = "/identities"
	RouteItem       = RouteCollection + "/{id}"
	RouteCredential = RouteItem + "/credentials/{type}"
)
