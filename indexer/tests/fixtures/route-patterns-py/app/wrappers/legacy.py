import os

import requests

LEGACY_URL = os.environ.get("LEGACY_API_URL", "")


def legacy_get(path):
    return requests.get(LEGACY_URL + path, timeout=5)


def ping():
    return legacy_get("/health")


def legacy_send(path, method="POST", body=None):
    return requests.request(method, LEGACY_URL + path, json=body)


def publish(event):
    legacy_send("/v2/events", body=event)
    legacy_send(f"/v2/events/{event['id']}", "DELETE")
