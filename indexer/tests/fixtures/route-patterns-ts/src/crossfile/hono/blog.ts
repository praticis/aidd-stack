import { Hono } from 'hono';

// A router named like a client and typed with generics: GET /blog/posts; a regex constraint: GET /blog/posts/{id}.
const api = new Hono<{ Bindings: Bindings }>();
api.get('/posts', listPosts);
api.get('/posts/:id{[0-9]+}', getPost);
export default api;

function listPosts() {}
function getPost() {}
