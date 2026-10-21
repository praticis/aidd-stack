package main

import "net/http"

func listItems(w http.ResponseWriter, r *http.Request) {}

func routesOnTheBranch(mux *http.ServeMux) {
	mux.HandleFunc("GET /v1/orders/{id}/items", listItems)
}
