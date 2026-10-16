package main

import (
	"net/http"

	"example.com/routepatterns/internal/web"
)

// gitea's route chain: m.Combo(path, middleware...) and a route per verb after it, inside groups or not.
func main() {
	m := web.NewRouter()
	m.Group("/notifications", func() {
		m.Combo("").
			Get(reqToken(), listNotifications).
			Put(reqToken(), readNotifications)
		m.Combo("/threads/{id}").Get(getThread).Patch(reqToken(), readThread)
	})
	m.Combo("/token", reqToken()).Delete(deleteToken)
	http.ListenAndServe(":3000", m)
}

func reqToken() func(http.Handler) http.Handler     { return nil }
func listNotifications(w http.ResponseWriter, r *http.Request) {}
func readNotifications(w http.ResponseWriter, r *http.Request) {}
func getThread(w http.ResponseWriter, r *http.Request)         {}
func readThread(w http.ResponseWriter, r *http.Request)        {}
func deleteToken(w http.ResponseWriter, r *http.Request)       {}
