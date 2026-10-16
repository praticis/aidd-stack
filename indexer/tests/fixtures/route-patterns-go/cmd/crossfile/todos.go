package main

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

type todosResource struct{}

type usersResource struct{}

// Routes is mounted by main at /todos: its root is GET /todos.
func (rs todosResource) Routes() chi.Router {
	r := chi.NewRouter()
	r.Get("/", rs.ListTodos)
	r.Get("/{id}", rs.GetTodo)
	return r
}

// The same method name on another type, mounted nowhere: its routes stay as written, its root is no route.
func (rs usersResource) Routes() chi.Router {
	r := chi.NewRouter()
	r.Get("/", rs.ListUsers)
	r.Get("/me", rs.Me)
	return r
}

func (rs todosResource) ListTodos(w http.ResponseWriter, req *http.Request) {}
func (rs todosResource) GetTodo(w http.ResponseWriter, req *http.Request)   {}
func (rs usersResource) ListUsers(w http.ResponseWriter, req *http.Request) {}
func (rs usersResource) Me(w http.ResponseWriter, req *http.Request)        {}
