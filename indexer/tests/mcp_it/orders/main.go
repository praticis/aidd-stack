package main

import "net/http"

func loadOrder(id string) string {
	return id
}

func getOrder(w http.ResponseWriter, r *http.Request) {
	_ = loadOrder(r.PathValue("id"))
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /v1/orders/{id}", getOrder)
	_ = http.ListenAndServe(":8080", mux)
}
