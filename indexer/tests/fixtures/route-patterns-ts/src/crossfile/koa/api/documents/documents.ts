import Router from "@koa/router";

const router = new Router();
const auth = () => async (_ctx: unknown, next: () => Promise<void>) => next();

async function documentsInfo(ctx: { body: unknown }) {
  ctx.body = {};
}

async function documentsList(ctx: { body: unknown }) {
  ctx.body = [];
}

router.post("documents.info", auth(), documentsInfo); // RPC style, no leading slash: POST /api/documents.info
router.post("documents.list", documentsList);

export default router;
