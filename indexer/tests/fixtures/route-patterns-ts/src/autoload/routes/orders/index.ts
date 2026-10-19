import { FastifyPluginAsync } from 'fastify'

const plugin: FastifyPluginAsync = async (fastify) => {
  fastify.get('/', async () => [])
  fastify.post('/', async () => ({}))
  fastify.get('/:id', async () => ({}))
}

export default plugin
