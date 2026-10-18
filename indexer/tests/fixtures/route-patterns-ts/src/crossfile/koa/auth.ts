import Koa from "koa";
import Router from "@koa/router";

const app = new Koa();
const router = new Router();

async function authRedirect(ctx: { redirect: (url: string) => void }) {
  ctx.redirect("/");
}

async function authNotFound(ctx: { status: number }) {
  ctx.status = 404;
}

router.get("/redirect", authRedirect); // GET /auth/redirect, through koa-mount in web.ts
router.all("{/*path}", authNotFound); // path-to-regexp 8: an optional wildcard, /auth/{rest}
app.use(router.routes());

export default app;
