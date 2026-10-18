module.exports = function (router) {
  router.get('/legacy/ping', ping);
};

function ping() {}
