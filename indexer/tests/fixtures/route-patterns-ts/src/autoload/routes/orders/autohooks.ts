import { FastifyInstance } from 'fastify'

export default async function (fastify: FastifyInstance) {
  fastify.addHook('onRequest', async () => {})
}
