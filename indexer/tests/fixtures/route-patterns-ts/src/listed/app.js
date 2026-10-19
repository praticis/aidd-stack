const express = require('express');
const routes = require('./routes');

const app = express();

app.use('/v4', routes);

module.exports = app;
