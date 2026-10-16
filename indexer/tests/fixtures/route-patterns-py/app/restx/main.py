from flask import Flask

from app.restx.api import api

app = Flask(__name__)
app.register_blueprint(api)
