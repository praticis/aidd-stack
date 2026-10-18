import Router from "@koa/router";

const router = new Router();

async function orphansList(ctx: { body: unknown }) {
  ctx.body = [];
}

router.post("orphans.list", orphansList); // mounted nowhere: no "/" ever comes before it, so no route
