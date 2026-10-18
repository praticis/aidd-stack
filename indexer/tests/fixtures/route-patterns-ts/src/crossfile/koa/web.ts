import Koa from "koa";
import mount from "koa-mount";
import api from "./api";
import auth from "./auth";

export default function init(app: Koa = new Koa()) {
  app.use(mount("/api", api)); // koa-mount: the API application under /api
  app.use(mount("/auth", auth));
  return app;
}
