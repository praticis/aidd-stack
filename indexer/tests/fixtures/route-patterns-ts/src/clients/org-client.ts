import axios from "axios";

const instance = axios.create({
  baseURL: "/api/v1",
});

instance.interceptors.request.use(function (config) {
  config.url = `${currentOrganization()}${config.url}`; // the url is rewritten at runtime: the base is not all that goes before it
  return config;
});

function currentOrganization() {
  return "default";
}

export default instance;
