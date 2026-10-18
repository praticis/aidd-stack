import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()
client = TestClient(app)


def smoke():
    # requests through a TestClient exercise this app; they are not outbound calls
    client.get("/items/1")
    with TestClient(app) as tc:
        tc.post("/items")


def stock():
    return httpx.get("http://inventory/v1/stock?sku=1")  # a literal query string: GET /v1/stock


def dev_email_log():
    # a development view driving this app through Django's test client (zulip): not an outbound call
    from django.test import Client

    dev_client = Client()
    dev_client.post("/accounts/password/reset/", {"email": "someone@example.com"})


def verify_transfer(hostname, token):
    from urllib.parse import urljoin

    # urljoin onto an absolute path keeps only the base's host: GET /api/v1/services/verify/{param}
    return httpx.get(urljoin(f"https://{hostname}", f"/api/v1/services/verify/{token}/"))


def admin_page(token):
    # a URL whose path is no route a server could have (`=` in the path): no call
    return httpx.get(f"https://example.com/admin/{token}god_mode=true")
