import { Hono } from 'hono';

// Routes chained on the constructor, exported by name: GET /api/todos, POST /api/todos/{id}/complete.
export const TodoAPI = new Hono<{ Bindings: Env }>()
  .get('/todos', listTodos)
  .post('/todos/:id/complete', completeTodo);

function listTodos() {}
function completeTodo() {}
