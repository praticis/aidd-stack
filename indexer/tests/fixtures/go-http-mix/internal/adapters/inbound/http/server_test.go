package httpapi
func TestX(t *testing.T) { mux.HandleFunc("GET /should/not/appear", nil) }
