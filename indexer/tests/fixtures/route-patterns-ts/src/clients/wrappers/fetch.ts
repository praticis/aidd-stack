type RequestOpts = { method?: string; data?: unknown; headers?: Record<string, string> };

// the verb is an option with a default; the named helpers give it
export function request(url: string, {method = 'GET', data, headers = {}, ...other}: RequestOpts = {}): Promise<Response> {
  return fetch(url, {method, headers, ...other, body: JSON.stringify(data)});
}

export const GET = (url: string, opts?: RequestOpts) => request(url, {method: 'GET', ...opts});
export const POST = (url: string, opts?: RequestOpts) => request(url, {method: 'POST', ...opts});
