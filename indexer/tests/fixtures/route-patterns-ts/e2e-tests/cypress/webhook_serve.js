// A webhook server the e2e tests start (mattermost e2e-tests/cypress): test code, no route.
const express = require('express');

const app = express();
app.post('/message_menus', onMessageMenu);
app.listen(3000);

function onMessageMenu(req, res) {
  res.json({});
}
