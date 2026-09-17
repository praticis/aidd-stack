package httpapi

func registerGin(r *gin.Engine, h *Handlers) {
	v1 := r.Group("/api/v1")
	v1.GET("/orders/:id", h.getOrder)
	v1.POST("/orders", h.createOrder)
	r.Any("/ping", h.ping)
}

func registerChi(r chi.Router, h *Handlers) {
	r.Get("/chi/items", h.listItems)
	r.Post("/chi/items", h.createItem)
}

func registerGorilla(r *mux.Router, h *Handlers) {
	r.HandleFunc("/gorilla/things/{id}", h.getThing).Methods("GET")
	r.HandleFunc("/gorilla/things", h.createThing).Methods(http.MethodPost)
}
