from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass

from flask import current_app, request, session


@dataclass(frozen=True)
class TerminalState:
    provider: str
    sandbox_id: str | None
    terminal_pid: int | None
    connected_at_ms: int
    last_io_at_ms: int


class TerminalRegistry:
    _lock = threading.Lock()
    _by_browser_id: dict[str, TerminalState] = {}

    @classmethod
    def set_active(cls, *, browser_id: str, state: TerminalState) -> None:
        if not browser_id:
            raise ValueError("Missing browser_id")
        with cls._lock:
            cls._by_browser_id[browser_id] = state

    @classmethod
    def touch(cls, *, browser_id: str) -> None:
        if not browser_id:
            return
        with cls._lock:
            st = cls._by_browser_id.get(browser_id)
            if st is None:
                return
            cls._by_browser_id[browser_id] = TerminalState(
                provider=st.provider,
                sandbox_id=st.sandbox_id,
                terminal_pid=st.terminal_pid,
                connected_at_ms=st.connected_at_ms,
                last_io_at_ms=int(time.time() * 1000),
            )

    @classmethod
    def get_active(cls, *, browser_id: str) -> TerminalState | None:
        if not browser_id:
            return None
        with cls._lock:
            return cls._by_browser_id.get(browser_id)

    @classmethod
    def clear_active(cls, *, browser_id: str) -> None:
        if not browser_id:
            return
        with cls._lock:
            cls._by_browser_id.pop(browser_id, None)


class TerminalManager:
    """Central backend entrypoint for terminal state + lifecycle.

    Design choice: WS-scoped terminal/sandbox lifecycle. Live state is tracked in
    a server-side registry keyed by browser_id (from Flask session).
    """

    @staticmethod
    def _ensure_browser_id() -> str:
        browser_id = str(session.get("browser_id") or "").strip()
        if not browser_id:
            browser_id = str(uuid.uuid4())
            session["browser_id"] = browser_id
        return browser_id

    @classmethod
    def get_active_sandbox_id(cls, *, browser_id: str) -> str | None:
        st = TerminalRegistry.get_active(browser_id=browser_id)
        sandbox_id = (st.sandbox_id if st is not None else None) or None
        if isinstance(sandbox_id, str) and sandbox_id.strip():
            return sandbox_id
        return None

    @classmethod
    def kill_active(cls, *, browser_id: str) -> bool:
        st = TerminalRegistry.get_active(browser_id=browser_id)
        if st is None:
            return False
        TerminalRegistry.clear_active(browser_id=browser_id)
        if st.provider in ("e2b", "e2b-sandbox") and st.sandbox_id:
            try:
                from e2b import Sandbox  # type: ignore

                return bool(Sandbox.kill(str(st.sandbox_id)))
            except Exception:
                return False
        return True

    @classmethod
    def handle_ws(cls, ws) -> None:
        """Single WS handler for /ws/terminal. Owns auth + provider dispatch."""
        browser_id = cls._ensure_browser_id()
        provider = str(current_app.config["TERMINAL_PROVIDER"]).strip().lower()

        def require_token() -> bool:
            return bool(current_app.config["TERMINAL_REQUIRE_TOKEN"])

        def enforce_origin() -> bool:
            return bool(current_app.config["TERMINAL_ENFORCE_ORIGIN"])

        if enforce_origin():
            origin = (request.headers.get("Origin") or "").strip()
            expected = request.host_url.rstrip("/")
            if not origin or origin.rstrip("/") != expected:
                try:
                    ws.send("\r\n\x1b[31mBlocked: invalid Origin.\x1b[0m\r\n")
                except Exception:
                    pass
                return

        if require_token():
            import time as _time

            token = (request.args.get("token") or "").strip()
            expected = session.get("terminal_ws_token") or ""
            exp = int(session.get("terminal_ws_token_exp") or 0)
            now = int(_time.time())
            if not token or token != expected or exp <= now:
                try:
                    ws.send("\r\n\x1b[31mBlocked: missing/invalid terminal token.\x1b[0m\r\n")
                except Exception:
                    pass
                return
            session.pop("terminal_ws_token", None)
            session.pop("terminal_ws_token_exp", None)

        if provider in ("disabled", "off", "none"):
            try:
                ws.send("\r\n\x1b[31mTerminal is disabled.\x1b[0m\r\n")
            except Exception:
                pass
            return

        # Defer implementation details to terminal_session module for now.
        from .terminal_session import handle_terminal_ws, handle_terminal_ws_e2b  # local import

        if provider in ("local", "local-pty", "pty"):
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
            handle_terminal_ws_e2b(ws, browser_id=browser_id)
            return

        try:
            ws.send(
                f"\r\n\x1b[31mUnknown TERMINAL_PROVIDER={provider!r}. "
                "Use 'local', 'e2b', or 'disabled'.\x1b[0m\r\n"
            )
        except Exception:
            pass
