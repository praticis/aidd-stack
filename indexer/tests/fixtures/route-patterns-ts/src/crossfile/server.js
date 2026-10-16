const express = require('express');

const app = express();
app.use('/v1', require('./v1'));            // a router required in place, its root too: GET /v1, GET /v1/status
const ops = express.Router();
ops.use(require('./health'));               // mounted without a path: GET /ops/healthz
app.use('/ops', ops);
const v2 = express.Router();
require('./legacy')(v2);                    // a router handed to another file's function: GET /v2/legacy/ping
app.use('/v2', v2);
