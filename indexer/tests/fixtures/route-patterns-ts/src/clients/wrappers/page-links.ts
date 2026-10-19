import {GET, POST} from './fetch';

const appSubUrl = window.config.appSubUrl;

// a link read from the page is a URL known only at run time: no call
export async function moveColumn(el: HTMLElement) {
  const link = el.getAttribute('data-url');
  await POST(`${link}/move`);
  await GET(`${el.dataset.treeLink}/tree-view`);
  await GET(`${appSubUrl}/user/settings/keys`);
}
