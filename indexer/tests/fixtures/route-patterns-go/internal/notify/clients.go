package notify

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"path"
	"strings"
)

// Requests whose path lives on a url.URL (alertmanager's notifiers, kratos' OIDC providers): set on its Path field,
// appended to it or joined to it, then read with String().
type Notifier struct {
	APIURL *url.URL
	client *http.Client
}

func (n *Notifier) token(ctx context.Context) error {
	u := *n.APIURL
	u.Path += "gettoken" // the configured URL ends in "/"
	_, err := Get(ctx, n.client, u.String())
	return err
}

func (n *Notifier) close(alias string) (*http.Request, error) {
	closeURL := *n.APIURL
	closeURL.Path += fmt.Sprintf("v2/alerts/%s/close", alias)
	return http.NewRequest("POST", closeURL.String(), nil)
}

func (n *Notifier) userinfo(ctx context.Context, issuer string) (*http.Request, error) {
	u, err := url.Parse(issuer)
	if err != nil {
		return nil, err
	}
	u.Path = path.Join(u.Path, "/oauth/userinfo")
	return http.NewRequestWithContext(ctx, "GET", u.String(), nil)
}

func (n *Notifier) post(ctx context.Context, body io.Reader) error {
	target := n.APIURL.JoinPath("api/v1/chat.postMessage").String()
	_, err := PostJSON(ctx, n.client, target, body)
	return err
}

// Not calls: a route registered on an API object (huma), a SQL query built around a column list, and a verb that
// is not HTTP read from a request object.
func notCalls(api *API, db *DB, cols []string) {
	Get(api, "/books", listBooks)
	db.Get(&post, "SELECT "+strings.Join(cols, ", ")+" FROM Posts ORDER BY CreateAt LIMIT 1")
}

func (n *Notifier) userinfoWithRequest(client *http.Client) {
	reqURL, _ := url.Parse("https://www.googleapis.com/oauth2/v1/userinfo")
	res := &http.Request{Method: "GET", URL: reqURL}
	client.Do(res)
}

// Get and PostJSON are the package's own helpers: the URL is the third argument.
func Get(ctx context.Context, client *http.Client, url string) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	return client.Do(req)
}

func PostJSON(ctx context.Context, client *http.Client, url string, body io.Reader) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, body)
	if err != nil {
		return nil, err
	}
	return client.Do(req)
}
