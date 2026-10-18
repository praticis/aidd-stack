from flask import Blueprint
from flask_restx import Api

from app.restx.challenges import challenges_namespace

api = Blueprint("api", __name__, url_prefix="/api/v2")
API_v2 = Api(api, version="v2")
API_v2.add_namespace(challenges_namespace, "/challenges")
