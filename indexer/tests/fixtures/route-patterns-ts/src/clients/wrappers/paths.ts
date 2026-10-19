import axios from 'axios';

// a helper that returns a path, a segment from its argument
function itemUrl(id: string): string {
  return `/catalog/items/${id}`;
}

const itemsRoot = () => '/catalog/items';

export function load(id: string) {
  return axios.get(itemUrl(id));
}

export function list() {
  return axios.get(`${itemsRoot()}/all`);
}
