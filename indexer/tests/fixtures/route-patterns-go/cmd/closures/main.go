package main

import (
	"net/http"

	"example.com/routepatterns/internal/web"
)

// A registration closure kept under a name, called inside groups or given as the body of one: its routes are on
// the outer `m`, under each use's prefix.
func main() {
	m := web.NewRouter()

	addHookRoutes := func() {
		m.Get("", listHooks)
		m.Post("/{id}/test", testHook)
	}
	m.Group("/{username}/{reponame}/hooks", func() {
		addHookRoutes()
	})
	m.Group("/-/admin/hooks", func() {
		addHookRoutes()
	})

	addViewRoutes := func() {
		m.Get("/posters", listPosters)
		m.Group("/{index}", func() {
			m.Get("/attachments/{uuid}", getAttachment)
		})
	}
	m.Group("/{username}/{reponame}/{type:issues}", addViewRoutes, reqSignIn())
	http.ListenAndServe(":3000", m)
}

func reqSignIn() func(http.Handler) http.Handler            { return nil }
func listHooks(w http.ResponseWriter, r *http.Request)      {}
func testHook(w http.ResponseWriter, r *http.Request)       {}
func listPosters(w http.ResponseWriter, r *http.Request)    {}
func getAttachment(w http.ResponseWriter, r *http.Request)  {}
