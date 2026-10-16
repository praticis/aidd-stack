from flask import Flask

from app.crossfile.blueprints import register_blueprints

app = Flask(__name__)
register_blueprints(app)  # the application handed to another module's function
