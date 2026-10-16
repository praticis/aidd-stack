from fastapi import APIRouter, FastAPI

app = FastAPI()
auth_router = APIRouter()


def register_user():
    return {}


REGISTRATION_ENABLED = True
if REGISTRATION_ENABLED:  # dispatch: the decorator applied by hand, only when a setting allows it
    register_user = auth_router.post("/register")(register_user)

app.include_router(auth_router, prefix="/auth")
