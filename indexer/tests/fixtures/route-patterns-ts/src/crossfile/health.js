const express = require('express');
const router = express.Router();
router.get('/healthz', healthz);
module.exports = router;

function healthz() {}
