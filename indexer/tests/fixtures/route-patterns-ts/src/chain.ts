import express from 'express';

// express: router.route(path) and a route per verb after it (express-boilerplate's user.route.js).
const app = express();
app
  .route('/members')
  .post(auth('manageUsers'), createUser)
  .get(auth('getUsers'), listUsers);
app.route('/members/:memberId').get(getUserById).delete(auth('manageUsers'), deleteUser);

function auth(right: string) { return (req, res, next) => next(); }
function createUser() {}
function listUsers() {}
function getUserById() {}
function deleteUser() {}
