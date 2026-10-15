package main

import (
	"net/http"

	"github.com/prometheus/common/route"
)

func main() {
	router := route.New()
	router.Get("/status", status)
	router.Del("/silence/:sid", deleteSilence) // Prometheus route: Del is DELETE
	http.ListenAndServe(":9093", router)
}

// A literal query string does not make the template invalid.
func openInvoices() (*http.Response, error) {
	return http.Get("http://billing/v1/invoices?status=open")
}

func status(w http.ResponseWriter, r *http.Request)        {}
func deleteSilence(w http.ResponseWriter, r *http.Request) {}
