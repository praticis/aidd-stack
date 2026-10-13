import express from 'express';
import axios from 'axios';
const app = express();
const router = express.Router();
const ORDERS_PATH = '/v1/orders';

router.get('/v1/health', (req, res) => res.send('ok'));
app.post('/v1/checkout', async (req, res) => {
  const r = await axios.post(`${process.env.SVC_URL}/v1/auth/failed-attempt`, req.body);
  const o = await axios.get(ORDERS_PATH + '/' + req.params.id);
  const f = await fetch(process.env.SVC_URL + '/v1/users/' + req.params.id, { method: 'DELETE' });
  res.json({ r, o, f });
});
