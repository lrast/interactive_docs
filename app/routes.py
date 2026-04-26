from flask import Blueprint, render_template, session

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route('/reset')
def reset_session():
    session.clear()
    return "Session cleared"
