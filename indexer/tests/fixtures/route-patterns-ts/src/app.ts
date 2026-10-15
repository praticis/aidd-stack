import express, { Request, Response } from 'express';

const app = express();
app.get('/', home);                // the application itself: GET /
app.get('/users/:id?', getUser);   // an optional parameter: GET /users/{id}

// A sub-router's "/" is where the file mounts it: GET /orders.
const orders = express.Router();
orders.get('/', listOrders);
app.use('/orders', orders);

// A router named like a client is still a router (its prefix comes from where it is mounted).
const api = express.Router();
api.get('/status', status);

// Express 5 optional groups.
app.get('/search/{:query}', search);
app.get('/files/:name{.:ext}', getFile);

// fetch without a method is a GET; with a method it is that one; with one we cannot read, it stays unknown.
export async function load(verb: string) {
  await fetch('/api/orders');
  await fetch('/api/orders', { method: 'POST' });
  await fetch('/api/items', { method: verb });
  await fetch(`/api/users?active=${true}`);
}

function home(req: Request, res: Response) {}
function search(req: Request, res: Response) {}
function getFile(req: Request, res: Response) {}
function getUser(req: Request, res: Response) {}
function listOrders(req: Request, res: Response) {}
function status(req: Request, res: Response) {}

app.listen(3000);
