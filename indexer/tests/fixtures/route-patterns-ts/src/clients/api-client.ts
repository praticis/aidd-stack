import axios, { AxiosInstance } from "axios";

const api: AxiosInstance = axios.create({
  baseURL: "/api", // every request of this client is under /api
  withCredentials: true,
});

export default api;
