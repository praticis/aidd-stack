package main

import (
	"context"
	"fmt"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

func main() {
	g := gin.New()
	g.GET(RouteItem, getIdentity)
	g.DELETE(RouteCredential, deleteCredential)
	g.Group("/user").Use(requireAdmin).POST("", createUser) // the group prefix carries through the chain

	mux := http.NewServeMux()
	mux.Handle("/booking/v1/", bookingHandler()) // a subtree handed to a sub-router: a mount, not a route
	http.Handle("/uppercase", uppercaseHandler)  // the default mux
	http.HandleFunc("/count", count)
	http.Handle("/", mux)
	http.ListenAndServe(":8080", nil)
}

// A spread handler list is a route registration on an unknown router, not an outbound GET (gitea web.go).
func register(routes *Router, mid []any) {
	routes.Get("/metrics", append(mid, metrics)...)
}

type service struct{ state *Cache }

// A cache read keyed by a joined string is not an HTTP GET (argo-cd repository.go).
func (s *service) check(root, version string, skip ...string) {
	key := root + "/" + version + "/" + strings.Join(skip, ",")
	s.state.Get(key)
}

var uppercaseHandler = http.HandlerFunc(count)

func getIdentity(c *gin.Context)                     {}
func deleteCredential(c *gin.Context)                {}
func createUser(c *gin.Context)                      {}
func requireAdmin(c *gin.Context)                    {}
func bookingHandler() http.Handler                   { return nil }
func count(w http.ResponseWriter, r *http.Request)   {}
func metrics(w http.ResponseWriter, r *http.Request) {}

// The base URL comes from a call; the path appended with += is what the code holds (argo-cd bitbucket_cloud.go).
func (c *client) contents(owner, repo string) (*http.Response, error) {
	urlStr := c.baseURL()
	urlStr += fmt.Sprintf("/repositories/%s/%s/src", owner, repo)
	req, _ := http.NewRequestWithContext(context.Background(), http.MethodGet, urlStr, nil)
	return http.DefaultClient.Do(req)
}

type client struct{}

func (c *client) baseURL() string { return "" }

// The prefix is a parameter: appending "/" and "*" to it makes no route of its own (chi _examples/fileserver).
func fileServer(r *Router, path string) {
	if path[len(path)-1] != '/' {
		path += "/"
	}
	path += "*"
	r.Get(path, func(w http.ResponseWriter, r *http.Request) {})
}
