import path from 'node:path'
import Fastify from 'fastify'
import fastifyAutoload from '@fastify/autoload'

const app = Fastify()

// every file under routes/ is a plugin, under its folder's path
app.register(fastifyAutoload, {
  dir: path.join(import.meta.dirname, 'routes'),
  autoHooks: true,
  options: { prefix: '/shop' }
})

app.get('/status/live', async () => ({ ok: true }))
