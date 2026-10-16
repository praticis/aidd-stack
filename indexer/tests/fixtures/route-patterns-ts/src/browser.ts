import axios from 'axios';
import $ from 'jquery';

const config = { get: (key: string) => key };

export function checkSubdomain(subdomain: string) {
  const url = '/json/realm/subdomain/' + subdomain;
  $.get(url, (response: unknown) => console.log(response)); // jQuery in the browser: a call, not a route
}

export function deleteApp(id: string) {
  return axios.delete(`${config.get('url')}application/${id}`); // a path, not a MIME type
}

export function clearMessages() {
  return axios.delete(config.get('url') + 'message'); // base URL + one relative segment
}

export async function fetchEmojiset(url: string) {
  return fetch(url); // a parameter, not the `url` of another function
}

export function changePassword(requests: any) {
  return requests
    .put('/account/password') // the receiver on the line above
    .send({});
}

export function removePlugin(api: any, id: string) {
  return api.del(`/admin/plugins/${id}`); // `del` is DELETE
}

export function updateTeam(CTFd: any) {
  let method = 'PATCH';
  let url = '/api/v1/teams/me';
  return CTFd.fetch(url, { method: method }); // the method held in a variable
}

export function createUser(CTFd: any, notify: boolean) {
  let url = '/api/v1/users';
  if (notify) {
    url = `${url}?notify=true`; // the template reads the earlier value
  }
  return CTFd.fetch(url, { method: 'POST' });
}

export function teamMembers(CTFd: any, id: string) {
  let url = '/api/v1/teams';
  url = url + '/' + id + '/members';
  return CTFd.fetch(url);
}

const API_PATH = 'api/v2';

export async function apiFetch(pathPrefix: string, path: string) {
  return fetch(`${pathPrefix}/${API_PATH}${path}`); // a generic wrapper: no path of its own (alertmanager)
}

export function savePage(CTFd: any, part: string) {
  let target = '/api/v1/pages';
  let method = 'POST';
  if (part) {
    target += '/' + part; // path and method from the same (last) assignments
    method = 'PATCH';
  }
  return CTFd.fetch(target, { method: method });
}

const resource = 'cases';

export const caseApi = {
  join: (API: any, caseId: string) => API.post(`/${resource}/${caseId}/join`, {}), // a word constant, one whole segment
  all: (API: any) => API.get(`/${resource}`),
  byName: (API: any) => API.get(resource), // a word alone is not a path
  tagged: (API: any, tag: string) => API.get(`/${resource}-${tag}`), // not a whole segment
};

const GHOST_URL = 'http://localhost:2368';

export async function adminRequest(endpoint: string) {
  const separator = endpoint.includes('?') ? '&' : '?';
  return fetch(`${GHOST_URL}/ghost/api/admin/${endpoint}${separator}god_mode=true`); // the rest of the path is the caller's
}
