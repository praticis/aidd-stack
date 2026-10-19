export const PATCH = async (req: Request) => Response.json({})

async function remove() {
  return new Response(null, { status: 204 })
}

export { remove as DELETE }
