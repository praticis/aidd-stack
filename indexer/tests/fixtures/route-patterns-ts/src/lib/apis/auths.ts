import { WEBUI_API_BASE_URL } from "$lib/constants"; // SvelteKit's $lib: src/lib

export const getSessionUser = async (token: string) => {
  const res = await fetch(`${WEBUI_API_BASE_URL}/auths/`, { method: "GET", headers: { Authorization: token } });
  return res.json();
};

export const getUsers = async (query?: string) => {
  const res = await fetch(`${WEBUI_API_BASE_URL}/users/all${query ? `?${query}` : ""}`); // the query is no segment
  return res.json();
};
