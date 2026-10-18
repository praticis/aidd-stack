from .cache import Cache
from .legacy import legacy_get
from .partner import PartnerClient

partner = PartnerClient("http://partner")
cache = Cache()


def invoices(customer_id: str):
    return legacy_get(f"/v2/customers/{customer_id}/invoices")


def refund(order_id: str):
    return partner._request("POST", f"/v1/orders/{order_id}/refund")


def cached_user():
    return cache.get("/v1/users/me")              # a class of the repo, but not a client wrapper


class Notifier:
    def __init__(self):
        self.partner = PartnerClient("http://partner")

    def notify(self, order_id: str):
        return self.partner._get(f"/v1/orders/{order_id}/notify")
