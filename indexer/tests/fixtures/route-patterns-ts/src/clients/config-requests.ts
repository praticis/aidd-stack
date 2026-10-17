import axios from 'axios';
import * as channel from './channel';

// Requests described by an object: the url is the request, whatever the receiver is called.
export function createBot(formData: FormData) {
  void channel.post({ url: "/json/bots", data: formData });
}

export function login(name: string) {
  return axios.create().request({ url: config.get('url') + 'auth/local/login', method: 'POST', data: { name } });
}

export function suggest() {
  return $.ajax((registry || 'https://packages.example.org') + '/api/v1/suggest', { type: 'GET' });
}
