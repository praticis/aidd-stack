const express = require('express');

const router = express.Router();

router
  .route('/:userId')
  .get((req, res) => res.send('user'))
  .delete((req, res) => res.send('gone'));

module.exports = router;
