import { FastifyPluginAsync } from 'fastify'

const plugin: FastifyPluginAsync = async (fastify) => {
  fastify.get('/:id/items', async () => [])
}

export default plugin
