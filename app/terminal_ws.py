import time

from flask import current_app, request, session
from flask_sock import Sock

from .terminal_session import handle_terminal_ws, handle_terminal_ws_e2b


def register_terminal_ws(app) -> Sock:
    sock = Sock(app)

    @sock.route("/ws/terminal")
    def terminal(ws):
        provider = str(current_app.config["TERMINAL_PROVIDER"]).strip().lower()

        def require_token() -> bool:
            return bool(current_app.config["TERMINAL_REQUIRE_TOKEN"])

        def enforce_origin() -> bool:
            return bool(current_app.config["TERMINAL_ENFORCE_ORIGIN"])

        if enforce_origin():
            origin = (request.headers.get("Origin") or "").strip()
            # Browsers set Origin for WebSockets; require it to match this host.
            expected = request.host_url.rstrip("/")
            if not origin or origin.rstrip("/") != expected:
                try:
                    ws.send("\r\n\x1b[31mBlocked: invalid Origin.\x1b[0m\r\n")
                except Exception:
                    pass
                return

        if require_token():
            token = (request.args.get("token") or "").strip()
            expected = session.get("terminal_ws_token") or ""
            exp = int(session.get("terminal_ws_token_exp") or 0)
            now = int(time.time())
            if not token or token != expected or exp <= now:
                try:
                    ws.send("\r\n\x1b[31mBlocked: missing/invalid terminal token.\x1b[0m\r\n")
                except Exception:
                    pass
                return
            # One-time token: prevent replays.
            session.pop("terminal_ws_token", None)
            session.pop("terminal_ws_token_exp", None)

        if provider in ("disabled", "off", "none"):
            try:
                ws.send("\r\n\x1b[31mTerminal is disabled.\x1b[0m\r\n")
            except Exception:
                pass
            return

        # Keep the existing local PTY behavior as an explicit dev-only option.
        if provider in ("local", "local-pty", "pty"):
            # Optional safety guard: refuse non-loopback access unless explicitly allowed.
            allow_remote = bool(current_app.config["TERMINAL_ALLOW_REMOTE"])
            remote_addr = request.remote_addr or ""
            if not allow_remote and remote_addr not in ("127.0.0.1", "::1"):
                try:
                    ws.send(
                        "\r\n\x1b[31mLocal PTY terminal is localhost-only. "
                        "Set TERMINAL_ALLOW_REMOTE=1 to override.\x1b[0m\r\n"
                    )
                except Exception:
                    pass
                return
            handle_terminal_ws(ws)
            return

        if provider in ("e2b", "e2b-sandbox"):
            handle_terminal_ws_e2b(ws)
            return

        try:
            ws.send(
                f"\r\n\x1b[31mUnknown TERMINAL_PROVIDER={provider!r}. "
                "Use 'local', 'e2b', or 'disabled'.\x1b[0m\r\n"
            )
        except Exception:
            pass
        return

    return sock
