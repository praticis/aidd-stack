from .base import BaseClient


# The client of another service: the paths go through the base class's wrappers, the verb with them.
class PartnerClient(BaseClient):
    def get_order(self, order_id: str):
        return self._get(f"/v1/orders/{order_id}")

    def create_order(self, payload: dict):
        return self._request("POST", "/v1/orders", json=payload)
