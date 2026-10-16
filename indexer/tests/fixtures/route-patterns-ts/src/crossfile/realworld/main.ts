import express from 'express';
import routes from './routes';
import { webhooks } from './webhooks';

const app = express();
app.use(routes);
app.use(webhooks);          // a sub-router's root at the application's root: POST /
