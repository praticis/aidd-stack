package kitclient

import (
	"net/url"

	httptransport "github.com/go-kit/kit/transport/http"
)

// go-kit clients: the method in NewClient, the path on the URL or in the request encoder (another file).
func MakeClientEndpoints(instance string) error {
	tgt, err := url.Parse(instance)
	if err != nil {
		return err
	}
	tgt.Path = "" // the encoders set it
	httptransport.NewClient("POST", tgt, encodePostProfileRequest, decodeResponse)
	httptransport.NewClient("GET", tgt, encodeGetProfileRequest, decodeResponse)
	return nil
}

func makeFetchRoutes(instance string) {
	u, err := url.Parse(instance)
	if err != nil {
		panic(err)
	}
	if u.Path == "" {
		u.Path = "/paths"
	}
	httptransport.NewClient("GET", u, encodeRequest, decodeResponse)
}
