package main

import (
	"net/http"

	"example.com/routepatterns/internal/addsvc"
)

func main() {
	var (
		httpHandler = addsvc.NewHTTPHandler()
	)
	http.ListenAndServe(":8081", httpHandler)
}
