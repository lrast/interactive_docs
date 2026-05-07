from __future__ import annotations

import secrets
import time

from flask import Blueprint, current_app, jsonify, session
from flask_sock import Sock

from .terminal_manager import TerminalManager, TerminalRegistry


bp = Blueprint("terminal", __name__, url_prefix="/api/terminal")


@bp.post("/token")
def mint_terminal_ws_token():
    """Mint a short-lived, one-time token for the terminal WebSocket."""
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    ttl_seconds = int(current_app.config["TERMINAL_WS_TOKEN_TTL_SECONDS"])

    session["terminal_ws_token"] = token
    session["terminal_ws_token_exp"] = now + max(1, ttl_seconds)

    return jsonify({"token": token, "expiresInSeconds": max(1, ttl_seconds)})


@bp.post("/kill")
def kill_terminal_sandbox():
    """Best-effort kill of the current browser session's active terminal."""
    browser_id = str(session.get("browser_id") or "").strip()
    if not browser_id:
        return jsonify({"killed": False})
    killed = bool(TerminalManager.kill_active(browser_id=browser_id))
    return jsonify({"killed": killed})


@bp.get("/active")
def get_active_terminal_state():
    """Lightweight debug/status endpoint for the UI (optional)."""
    browser_id = str(session.get("browser_id") or "")
    st = TerminalRegistry.get_active(browser_id=browser_id)
    return jsonify(
        {
            "browserId": browser_id,
            "active": st is not None,
            "provider": (st.provider if st else None),
            "sandboxId": (st.sandbox_id if st else None),
        }
    )


def register_terminal_ws(app) -> Sock:
    sock = Sock(app)

    @sock.route("/ws/terminal")
    def terminal(ws):
        TerminalManager.handle_ws(ws)

    return sock

