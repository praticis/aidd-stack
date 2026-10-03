package httpapi

import "net/http"

// handler registered in document_handler.go, defined here (same package, other file)
func (h *DocumentHandler) savePassword(w http.ResponseWriter, r *http.Request) {}
