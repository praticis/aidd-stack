from fastapi import APIRouter, FastAPI
from flask import Blueprint, Flask

api = FastAPI()
users = APIRouter()


@users.get("/")
def list_users(): ...  # GET /users — the router is included below


@users.get("/{user_id}")
def get_user(user_id: int): ...  # GET /users/{user_id}


api.include_router(users, prefix="/users")

web = Flask(__name__)
admin = Blueprint("admin", __name__)


@admin.route("/dashboard")
def dashboard(): ...  # GET /admin/dashboard


web.register_blueprint(admin, url_prefix="/admin")
