import os
import uuid
from datetime import timedelta

from flask import Flask, request, session


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-in-production")
    app.config["SESSION_COOKIE_NAME"] = "interactive_docs_session"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get(
        "FLASK_SESSION_COOKIE_SECURE", ""
    ).lower() in ("1", "true", "yes")
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        days=int(os.environ.get("SESSION_LIFETIME_DAYS", "31"))
    )

    @app.before_request
    def ensure_browser_session() -> None:
        if request.path.startswith("/static/"):
            return
        session.permanent = True
        session.setdefault("browser_id", str(uuid.uuid4()))
        session.setdefault("chat_history", [])
        session.setdefault("test", 'test')

    from . import chat, routes, terminal_ws

    app.register_blueprint(routes.bp)
    app.register_blueprint(chat.bp)
    terminal_ws.register_terminal_ws(app)

    return app
