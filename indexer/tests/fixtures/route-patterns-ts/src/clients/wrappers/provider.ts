// the verb is in the options the caller hands on, spread into the request's own
export async function fetchProvider(url: string, options: RequestInit): Promise<unknown> {
  const response = await fetch(url, { ...options, signal: AbortSignal.timeout(1000) });
  return response.json();
}

export function upload(body: FormData) {
  return fetchProvider('https://files.example.com/v1/files', { method: 'POST', body });
}
