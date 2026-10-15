import express from 'express';
import Fastify from 'fastify';
import { Hono } from 'hono';

// fastify: a plugin registered with a prefix (GET /english/hello).
const fastify = Fastify();
fastify.register(function (instance, opts, done) {
  instance.get('/hello', hello);
  done();
}, { prefix: '/english' });

// Hono: basePath on the app and a sub-app mounted with route() (POST /api/hello, GET /api/book, GET /api/book/{id}).
const app = new Hono().basePath('/api');
app.post('/hello', helloHono);
const book = new Hono();
book.get('/', listBooks);
book.get('/:id', showBook);
app.route('/book', book);

// express: the router mounted in the same scope, before its routes (GET /v3/config).
export default function (server: express.Express) {
  const router = express.Router();
  server.use('/v3', router);
  router.get('/config', getConfig);
}

function hello() {}
function helloHono() {}
function listBooks() {}
function showBook() {}
function getConfig() {}
