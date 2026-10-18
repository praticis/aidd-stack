import API from "./org-client";

export default {
  getAll() {
    return API.get("/cases"); // as written: GET /cases
  },
};
