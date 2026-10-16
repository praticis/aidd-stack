const router = require('express').Router();
router.get('/', v1Root);
router.get('/status', v1Status);
module.exports = router;

function v1Root() {}
function v1Status() {}
