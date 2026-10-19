const express = require('express');
const authRoute = require('./auth.route');
const userRoute = require('./user.route');
const docsRoute = require('./docs.route');
const pluginRoutes = require('./plugins');

const router = express.Router();

// sub-routers kept in a list and mounted in a loop
const defaultRoutes = [
  {
    path: '/auth',
    route: authRoute,
  },
  {
    path: '/users',
    route: userRoute,
  },
];

defaultRoutes.forEach((route) => {
  router.use(route.path, route.route);
});

const devRoutes = [{ path: '/docs', route: docsRoute }];

for (const r of devRoutes) {
  router.use(r.path, r.route);
}

// a list built at run time: nothing to read
pluginRoutes.load().forEach((p) => {
  router.use(p.path, p.router);
});

module.exports = router;
