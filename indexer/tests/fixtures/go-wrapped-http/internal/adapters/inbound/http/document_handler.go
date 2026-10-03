package httpapi

import "net/http"

const documentsBase = "/v1/onboardings/{onboardingId}/documents/{documentId}"

type DocumentHandler struct{}

func (h *DocumentHandler) registerRoutes(sc *ServerConfig, mux *http.ServeMux) {
	mux.Handle("PUT "+documentsBase+"/ocr-reference", sc.setHandlerSecurity(h.registerOCRReference))
	mux.Handle(http.MethodPost+" "+documentsBase+"/upload", sc.setHandlerSecurity(h.uploadDocument))
	mux.Handle("POST /v1/onboardings/{onboardingId}/steps/password", sc.setHandlerSecurity(h.savePassword))
}

func (h *DocumentHandler) registerOCRReference(w http.ResponseWriter, r *http.Request) {}
func (h *DocumentHandler) uploadDocument(w http.ResponseWriter, r *http.Request)       {}
