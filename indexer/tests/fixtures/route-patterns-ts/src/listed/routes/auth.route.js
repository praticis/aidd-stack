const express = require('express');

const router = express.Router();

router.post('/login', (req, res) => res.send('ok'));
router.post('/logout', (req, res) => res.send('ok'));

module.exports = router;
