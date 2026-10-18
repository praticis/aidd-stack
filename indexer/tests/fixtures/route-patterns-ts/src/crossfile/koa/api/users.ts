import Router from "koa-router";

const router = new Router();

async function usersMe(ctx: { body: unknown }) {
  ctx.body = {};
}

router.get("users.me", usersMe);

export default router;
