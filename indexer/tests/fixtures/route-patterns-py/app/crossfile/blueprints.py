from flask import Blueprint

reports = Blueprint("reports", __name__)


@reports.route("/monthly")  # GET /reports/monthly: registered by a function the app calls elsewhere
def monthly(): ...


def register_blueprints(app):
    app.register_blueprint(reports, url_prefix="/reports")
