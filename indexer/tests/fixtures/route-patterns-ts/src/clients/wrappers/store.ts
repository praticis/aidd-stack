import axios from 'axios';

const client = axios.create({ baseURL: '/rpc' });

// the client's base goes before the paths the subclasses hand to the store
export class Store {
  protected fetchPaginated(endpoint: string, params?: object) {
    return client.post(endpoint, params);
  }

  act(action: string) {
    return client.post(`/items.${action}`, {});
  }
}

export class GroupsStore extends Store {
  fetchPage() {
    return this.fetchPaginated('/groups.list');
  }
}
