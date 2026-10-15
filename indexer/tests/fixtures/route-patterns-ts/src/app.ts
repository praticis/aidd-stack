import express, { Request, Response } from 'express';

const app = express();
app.get('/', home);                // the application itself: GET /
app.get('/users/:id?', getUser);   // an optional parameter: GET /users/{id}

// A sub-router is mounted elsewhere: its "/" is not the application root.
const orders = express.Router();
orders.get('/', listOrders);
app.use('/orders', orders);

// A router named like a client is still a router (its prefix comes from where it is mounted).
const api = express.Router();
api.get('/status', status);

function home(req: Request, res: Response) {}
function getUser(req: Request, res: Response) {}
function listOrders(req: Request, res: Response) {}
function status(req: Request, res: Response) {}

app.listen(3000);
