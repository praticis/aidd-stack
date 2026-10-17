const router = require('express').Router();
router.get('/', v1Root);
router.get('/status', v1Status);
router.get('/reset/:code?', reset);         // GET /v1/reset/{code} and GET /v1/reset
module.exports = router;

function v1Root() {}
function v1Status() {}
function reset() {}
