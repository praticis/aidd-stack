import { Router } from 'express';

export const webhooks = Router();
webhooks.post('/', receiveWebhook);

function receiveWebhook() {}
