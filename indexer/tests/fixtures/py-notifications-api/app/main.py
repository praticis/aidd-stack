from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/v1/notifications")
def send(payload: dict):
    return payload
