from fastapi import FastAPI

from app.crossfile.api import api_router
from app.crossfile.config import settings

app = FastAPI()
app.include_router(api_router, prefix=settings.API_V1_STR)  # the prefix is a setting of another module

internal = FastAPI()


@internal.get("/status")  # GET /internal/status: a sub-application mounted below
def status(): ...


app.mount("/internal", app=internal)
