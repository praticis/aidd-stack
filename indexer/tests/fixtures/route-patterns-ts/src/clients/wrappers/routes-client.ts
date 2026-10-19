import { buildQueryString } from './query-string';

// route helpers of the client class, and a request method that takes the verb from the options it hands on
export class RoutesClient {
  url = '';
  urlVersion = '/api/v4';

  getBaseRoute() {
    return `${this.url}${this.urlVersion}`;
  }

  getUsersRoute() {
    return `${this.getBaseRoute()}/users`;
  }

  getUserRoute(userId: string) {
    return `${this.getUsersRoute()}/${userId}`;
  }

  getOptions(options: RequestInit) {
    return { ...options, credentials: 'include' as const };
  }

  private doFetchWithResponse = async (url: string, options: RequestInit) => {
    return fetch(url, this.getOptions(options));
  };

  protected doFetch = async (url: string, options: RequestInit) => {
    const response = await this.doFetchWithResponse(url, options);
    return response.json();
  };

  updateStatus = (userId: string) => {
    return this.doFetch(`${this.getUserRoute(userId)}/status`, { method: 'put' });
  };

  searchUsers = () => {
    return this.doFetch(`${this.getUsersRoute()}/search`, { method: 'post', body: '{}' });
  };

  listUsers = () => {
    return this.doFetch(this.getUsersRoute(), { headers: {} });
  };

  getTeamsRoute() {
    return `${this.getBaseRoute()}/teams`;
  }

  getTeamRoute(teamId: string) {
    return `${this.getTeamsRoute()}/${teamId}`;
  }

  getTeamMembersRoute(teamId: string) {
    return `${this.getTeamRoute(teamId)}/members`;
  }

  // the query string glued to the path is not part of it
  membersByIds = (teamId: string, ids: string[]) => {
    return this.doFetch(`${this.getTeamMembersRoute(teamId)}/ids${buildQueryString({ ids })}`, { method: 'post' });
  };

  autocomplete = (term: string) => {
    const query = buildQueryString({ term });
    return this.doFetch(`${this.getUsersRoute()}/autocomplete${query}`, { method: 'get' });
  };

  teamStats = (teamId: string, all = false) => {
    const param = all ? '' : '?exclude_deleted=true';
    return this.doFetch(`${this.getTeamRoute(teamId)}/stats${param}`, { method: 'get' });
  };

  purge = (ids: string[]) => {
    return this.doFetch(`${this.getBaseRoute()}/purge${ids.length ? '?ids=' + ids.join(',') : ''}`, { method: 'post' });
  };

  products = (legacy?: boolean) => {
    let query = '';
    if (legacy) {
      query = '?include_legacy=true';
    }
    return this.doFetch(`${this.getBaseRoute()}/products${query}`, { method: 'get' });
  };
}
