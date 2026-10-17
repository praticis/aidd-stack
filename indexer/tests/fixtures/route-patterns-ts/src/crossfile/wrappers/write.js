const router = require('express').Router();
const { setupApiRoute } = require('./helpers');

function routes() {
  setupApiRoute(router, 'post', '/', [], createUser);
  setupApiRoute(router, 'get', '/:uid', [], getUser);
  setupApiRoute(router, 'get', '/:uid/sessions/:sid?', [], listSessions);   // optional: with and without it
}

// The module's router, returned by the exported function.
module.exports = function () {
  routes();
  return router;
};

function createUser() {}
function getUser() {}
function listSessions() {}
