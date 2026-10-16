import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { TodoAPI } from './todo';
import blog from './blog';

export default new Hono<{}>()
  .use(cors())
  .route('/api', TodoAPI)
  .route('/blog', blog);
