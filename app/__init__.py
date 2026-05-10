import os
import uuid
from datetime import timedelta

from flask import Flask, request, session
from flask_session import Session


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-in-production")

    # Session settings
    app.config["SESSION_COOKIE_NAME"] = "interactive_docs_session"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = _env_bool("FLASK_SESSION_COOKIE_SECURE", False)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        days=_env_int("SESSION_LIFETIME_DAYS", 31)
    )
    ## Session storage settings
    app.config["SESSION_TYPE"] = os.environ.get("FLASK_SESSION_TYPE", "filesystem")
    app.config["SESSION_USE_SIGNER"] = True
    app.config["SESSION_PERMANENT"] = True
    if app.config["SESSION_TYPE"] == "filesystem":
        session_dir = os.environ.get(
            "FLASK_SESSION_FILE_DIR", os.path.join(app.instance_path, "sessions")
        )
        os.makedirs(session_dir, exist_ok=True)
        app.config["SESSION_FILE_DIR"] = session_dir

    # Terminal / sandbox settings (centralized env handling)
    terminal_provider = (os.environ.get("TERMINAL_PROVIDER") or "local").strip().lower()
    app.config["TERMINAL_PROVIDER"] = terminal_provider
    app.config["TERMINAL_ALLOW_REMOTE"] = _env_bool("TERMINAL_ALLOW_REMOTE", False)

    # Firecrawl (documentation iframe fallback when a URL is not embeddable)
    _fc_key = (os.environ.get("FIRECRAWL_API_KEY") or "").strip()
    app.config["FIRECRAWL_API_KEY"] = _fc_key or None

    # E2B settings (used when TERMINAL_PROVIDER=e2b)
    app.config["E2B_TEMPLATE_NAME"] = (os.environ.get("E2B_TEMPLATE_NAME") or "interactive-docs-ipython").strip()
    app.config["E2B_ALLOW_INTERNET_ACCESS"] = _env_bool("E2B_ALLOW_INTERNET_ACCESS", True)

    # Security defaults: token required by default for e2b, optional for local.
    require_token_default = terminal_provider in ("e2b", "e2b-sandbox")
    app.config["TERMINAL_REQUIRE_TOKEN"] = _env_bool(
        "TERMINAL_REQUIRE_TOKEN", require_token_default
    )
    app.config["TERMINAL_ENFORCE_ORIGIN"] = _env_bool("TERMINAL_ENFORCE_ORIGIN", True)
    app.config["TERMINAL_WS_TOKEN_TTL_SECONDS"] = _env_int(
        "TERMINAL_WS_TOKEN_TTL_SECONDS", 60
    )

    # Limits / abuse controls
    app.config["TERMINAL_MAX_SESSION_SECONDS"] = _env_int("TERMINAL_MAX_SESSION_SECONDS", 3600)
    app.config["TERMINAL_IDLE_TIMEOUT_SECONDS"] = _env_int("TERMINAL_IDLE_TIMEOUT_SECONDS", 300)
    app.config["TERMINAL_MAX_INBOUND_BYTES"] = _env_int("TERMINAL_MAX_INBOUND_BYTES", 65536)

    # Session-scoped E2B package install settings
    app.config["TERMINAL_MAX_PIP_REQUIREMENTS_LINES"] = _env_int(
        "TERMINAL_MAX_PIP_REQUIREMENTS_LINES", 50
    )
    app.config["TERMINAL_MAX_PIP_REQUIREMENT_LINE_CHARS"] = _env_int(
        "TERMINAL_MAX_PIP_REQUIREMENT_LINE_CHARS", 200
    )
    app.config["TERMINAL_PIP_INSTALL_TIMEOUT_SECONDS"] = _env_int(
        "TERMINAL_PIP_INSTALL_TIMEOUT_SECONDS", 600
    )

    Session(app)

    @app.before_request
    def ensure_browser_session() -> None:
        if request.path.startswith("/static/"):
            return
        session.permanent = True
        session.setdefault("browser_id", str(uuid.uuid4()))

    from . import chat, routes, terminal_routes

    app.register_blueprint(routes.bp)
    app.register_blueprint(chat.bp)
    app.register_blueprint(terminal_routes.bp)
    terminal_routes.register_terminal_ws(app)

    return app


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "")
    if raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes")

def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default
