import httpx


class BaseClient:
    def __init__(self, base_url: str):
        self.client = httpx.Client(base_url=base_url)

    def _request(self, method: str, path: str, **kwargs):
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    def _get(self, path: str):
        return self._request("GET", path)
