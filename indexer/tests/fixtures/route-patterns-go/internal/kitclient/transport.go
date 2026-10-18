package kitclient

import (
	"context"
	"net/http"
	"net/url"
)

func encodePostProfileRequest(ctx context.Context, req *http.Request, request interface{}) error {
	req.URL.Path = "/profiles/"
	return encodeRequest(ctx, req, request)
}

func encodeGetProfileRequest(ctx context.Context, req *http.Request, request interface{}) error {
	profileID := url.QueryEscape(request.(string))
	req.URL.Path = "/profiles/" + profileID
	return encodeRequest(ctx, req, request)
}

func encodeRequest(_ context.Context, req *http.Request, request interface{}) error { return nil }

func decodeResponse(_ context.Context, resp *http.Response) (interface{}, error) { return nil, nil }
