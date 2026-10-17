const express = require('express');
const helpers = require('./helpers');

const app = express();
const write = express.Router();
write.use('/api/v3/users', require('./write')());          // POST /api/v3/users, GET /api/v3/users/{uid}
app.use(write);
helpers.setupPageRoute(app, '/categories', [], listCategories);  // GET /categories and GET /api/categories

function listCategories() {}

// A request with a path, an identifier and three arguments is no wrapper call (k6's http.del).
const http = require('k6/http');
function removeGroup(id, params) {
  return http.del(`${API_URL}/public/groups/${id}`, null, params);
}

// A registration under a path its caller gives, with no call that gives one: the route stays as written.
function adminRoutes(router, name) {
  router.get(`/api/${name}/config`, adminConfig);
}
adminRoutes(app, 'admin');

function adminConfig() {}

// A path with a prefix only known at run time makes no route (`/{param}/settings` would link nothing).
function remountable(router, name) {
  helpers.setupPageRoute(router, `/${name}/settings`, [], settingsPage);
}
remountable(app, mounts.admin);

function settingsPage() {}
