// GET and POST /ghost/api/admin/posts: backend → api → admin, through two lazyUse and a re-export.
const express = require('express');

module.exports = function apiRoutes() {
  const router = express.Router('admin api');
  router.get('/posts', browsePosts);
  router.post('/posts', addPost);
  return router;
};

function browsePosts(req, res) {}
function addPost(req, res) {}
