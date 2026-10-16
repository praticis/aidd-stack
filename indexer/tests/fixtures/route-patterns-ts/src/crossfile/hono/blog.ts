import { Hono } from 'hono';

// A router named like a client and typed with generics: GET /blog/posts.
const api = new Hono<{ Bindings: Bindings }>();
api.get('/posts', listPosts);
export default api;

function listPosts() {}
