type Options = { baseUrl?: string };

class ApiClient {
  baseUrl: string;

  constructor(options: Options = {}) {
    this.baseUrl = options.baseUrl || "/api"; // the client's base: the option, else /api
  }

  post = (path: string, data?: unknown) => this.request(path, "POST", data);

  private request(path: string, method: string, data?: unknown) {
    return globalThis.fetch(this.baseUrl + path, { method, body: JSON.stringify(data) });
  }
}

export const client = new ApiClient();
export const apiV2 = new ApiClient({ baseUrl: "/api/v2" });
