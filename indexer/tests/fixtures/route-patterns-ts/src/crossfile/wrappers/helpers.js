// The project's own route helpers (NodeBB's src/routes/helpers.js): the registrations below are not routes.
const helpers = module.exports;

// router, name, middlewares (optional), controller: a page and its /api twin.
helpers.setupPageRoute = function (...args) {
  const [router, name] = args;
  const controller = args[args.length - 1];
  router.get(name, controller);
  router.get(`/api${name}`, controller);
};

// router, verb, name, middlewares (optional), controller
helpers.setupApiRoute = function (...args) {
  const [router, verb, name] = args;
  router[verb](name, args[args.length - 1]);
};
