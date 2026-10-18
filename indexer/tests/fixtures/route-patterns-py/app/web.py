from flask import Blueprint, Flask

app = Flask(__name__)


@app.route("/")  # the application itself: GET /
def index():
    return "ok"


@app.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])  # a converter: /posts/{post_id}/edit
def edit_post(post_id):
    return "ok"


@app.route("/<any(about, help):page>")  # a converter with arguments: GET /{page}
def static_page(page):
    return page


admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.route("/")  # the blueprint root, its prefix known: GET /admin
def admin_index():
    return "ok"


plain = Blueprint("plain", __name__)


@plain.route("/")  # no prefix here: registered elsewhere, its "/" is not a route
def plain_index():
    return "ok"
