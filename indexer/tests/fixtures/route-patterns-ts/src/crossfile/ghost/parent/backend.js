// The API mounted by the wrapper, under a constant of another directory.
const express = require('../express');
const { BASE_API_PATH } = require('../shared/url-utils');

module.exports = () => {
  const backendApp = express('backend');
  backendApp.lazyUse(BASE_API_PATH, require('../api'));
  return backendApp;
};
