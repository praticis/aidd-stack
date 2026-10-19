const express = require('express');

const router = express.Router();

router.get('/plugin-state', (req, res) => res.send('state'));

module.exports = { load: () => [{ path: '/plugins', router }] };
