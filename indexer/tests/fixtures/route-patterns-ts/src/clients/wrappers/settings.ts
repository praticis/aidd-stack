import {GET, POST, request} from './fetch';

const appSubUrl = window.config.appSubUrl;

export async function applyTheme(name: string) {
  await POST(`${appSubUrl}/-/web-theme/apply?theme=${encodeURIComponent(name)}`);
  const res = await GET(`${appSubUrl}/user/stopwatches`);
  await request(`${appSubUrl}/user/settings`, {method: 'PATCH'});
  await request('/user/avatar');
  return res;
}
