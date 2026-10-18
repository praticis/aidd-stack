// The app's own express (Ghost's shared/express): every app it builds mounts a module lazily under a path.
const express = require('express');

module.exports = function createApp(name) {
  const app = express();
  app.lazyUse = function lazyUse(mountPath, requireFn) {
    app.use(mountPath, (req, res, next) => requireFn()(req, res, next));
  };
  return app;
};
