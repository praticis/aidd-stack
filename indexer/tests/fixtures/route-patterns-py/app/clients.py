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
