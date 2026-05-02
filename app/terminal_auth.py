from __future__ import annotations

import secrets
import time

from flask import Blueprint, current_app, jsonify, session


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
    """Best-effort kill of the current browser session's E2B sandbox."""
    sandbox_id = session.pop("e2b_terminal_sandbox_id", None)
    if not sandbox_id:
        return jsonify({"killed": False})

    try:
        from e2b import Sandbox  # type: ignore

        killed = bool(Sandbox.kill(str(sandbox_id)))
        return jsonify({"killed": killed})
    except Exception:
        return jsonify({"killed": False})
