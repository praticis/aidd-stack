import Koa from "koa";
import Router from "@koa/router";
import documents from "./documents";
import users from "./users";

const api = new Koa();
const router = new Router();

router.use("/", documents.routes()); // @koa/router puts "/" before "documents.info" as written
router.use("/", users.middleware());

api.use(router.routes());
api.use(router.allowedMethods());

export default api;
