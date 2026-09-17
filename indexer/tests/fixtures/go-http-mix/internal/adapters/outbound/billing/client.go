package billing

import (
	"context"
	"fmt"
	"net/http"
	"os"
)

type Client struct{ baseURL string; hc *http.Client }

func New() *Client { return &Client{baseURL: os.Getenv("BILLING_BASE_URL")} }

func (c *Client) RegisterFailedAttempt(ctx context.Context, in any) error {
	var out any
	return c.PostJSON(ctx, routeFailedAttempt, in, &out)
}

func (c *Client) GetUser(ctx context.Context, id string) error {
	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+fmt.Sprintf(routeUserByID, id), nil)
	_, err := c.hc.Do(req)
	return err
}

func (c *Client) Ping(ctx context.Context) error {
	resp, err := c.hc.Get(c.baseURL + routeHealth)
	_ = resp
	return err
}

func (c *Client) Raw(ctx context.Context, id string) error {
	req, _ := http.NewRequest("DELETE", "https://billing.internal/v1/users/"+id+"/sessions", nil)
	_, err := c.hc.Do(req)
	return err
}

func (c *Client) PostJSON(ctx context.Context, path string, in, out any) error { return nil }
