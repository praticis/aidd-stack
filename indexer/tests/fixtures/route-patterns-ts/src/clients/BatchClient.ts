type Options = { baseUrl?: string };

export class BatchClient {
  baseUrl: string;

  constructor(options: Options = {}) {
    this.baseUrl = options.baseUrl || "/api";
  }

  fetch = async <T>(path: string, method: string, data?: unknown): Promise<T> => {
    const url = path.match(/^http/) ? path : this.baseUrl + path;
    const res = await globalThis.fetch(url, { method, body: JSON.stringify(data) });
    return res.json();
  };

  flush = async (requests: unknown[]) => {
    const res = await this.fetch<{ data: unknown[] }>("/batch", "POST", { requests }); // POST /api/batch
    return res.data;
  };
}
