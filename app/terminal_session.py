"""PTY-backed IPython session for WebSocket terminal (Unix only).

Resize control messages are JSON text: {"type":"resize","cols":N,"rows":M}.
All other inbound text is written to the PTY as UTF-8.
"""

from __future__ import annotations

import errno
import json
import os
import signal
import struct
import sys
import threading
import time

from typing import Any, Callable

from flask import Response, current_app, session

if sys.platform != "win32":
    import fcntl
    import pty
    import termios

def _force_save_session(*, hypothesis_id: str, location: str) -> None:
    """Persist session changes from WebSocket handlers.

    WebSocket routes don't always trigger Flask's normal response lifecycle,
    so Flask-Session may not write modified session data automatically.
    """
    try:
        app = current_app._get_current_object()
        resp = Response("")
        app.session_interface.save_session(app, session, resp)  # type: ignore[attr-defined]
    except Exception as e:
        # Fail-fast: if we can't persist the session, downstream requests won't see the sandbox.
        raise RuntimeError(f"Failed to persist session from WebSocket: {e}") from e


def _set_winsize(master_fd: int, rows: int, cols: int) -> None:
    if sys.platform == "win32":
        return
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)


def _maybe_resize_json(text: str) -> tuple[bool, int | None, int | None]:
    """If text is a resize control message, return (True, rows, cols)."""
    stripped = text.strip()
    if not stripped.startswith("{"):
        return False, None, None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return False, None, None
    if not isinstance(payload, dict) or payload.get("type") != "resize":
        return False, None, None
    try:
        rows = int(payload["rows"])
        cols = int(payload["cols"])
    except (KeyError, TypeError, ValueError):
        return False, None, None
    if rows <= 0 or cols <= 0:
        return False, None, None
    return True, rows, cols


def handle_terminal_ws(ws) -> None:
    if sys.platform == "win32":
        try:
            ws.send(
                "\r\n\x1b[31mIPython terminal is not supported on Windows "
                "(PTY required).\x1b[0m\r\n"
            )
        except Exception:
            pass
        return

    pid, master_fd = pty.fork()
    if pid == 0:
        os.environ.setdefault("TERM", "xterm-256color")
        os.environ.setdefault("COLORTERM", "truecolor")
        os.execlp("ipython", "ipython", "--no-confirm-exit")
        os._exit(127)

    stop = threading.Event()
    last_io_at = time.monotonic()
    started_at = time.monotonic()

    # Limits (configurable)
    max_session_seconds = int(current_app.config["TERMINAL_MAX_SESSION_SECONDS"])
    idle_timeout_seconds = int(current_app.config["TERMINAL_IDLE_TIMEOUT_SECONDS"])
    max_inbound_bytes = int(current_app.config["TERMINAL_MAX_INBOUND_BYTES"])

    def watchdog() -> None:
        while not stop.is_set():
            now = time.monotonic()
            if max_session_seconds > 0 and now - started_at > max_session_seconds:
                try:
                    ws.send("\r\n\x1b[31mTerminal session timed out.\x1b[0m\r\n")
                except Exception:
                    pass
                stop.set()
                return
            if idle_timeout_seconds > 0 and now - last_io_at > idle_timeout_seconds:
                try:
                    ws.send("\r\n\x1b[31mTerminal session idle timeout.\x1b[0m\r\n")
                except Exception:
                    pass
                stop.set()
                return
            time.sleep(1.0)

    def reader() -> None:
        while not stop.is_set():
            try:
                data = os.read(master_fd, 65536)
            except OSError as e:
                if e.errno == errno.EINTR:
                    continue
                break
            if not data:
                break
            try:
                ws.send(data.decode("utf-8", errors="replace"))
            except Exception:
                break
        stop.set()

    reader_thread = threading.Thread(target=reader, name="pty-reader", daemon=True)
    watchdog_thread = threading.Thread(target=watchdog, name="pty-watchdog", daemon=True)

    try:
        _set_winsize(master_fd, 24, 80)
    except OSError:
        pass

    reader_thread.start()
    watchdog_thread.start()

    try:
        while True:
            msg = ws.receive()
            if msg is None:
                break
            if isinstance(msg, bytes):
                if len(msg) > max_inbound_bytes:
                    try:
                        ws.send("\r\n\x1b[31mInput too large.\x1b[0m\r\n")
                    except Exception:
                        pass
                    break
                text = msg.decode("utf-8", errors="replace")
            else:
                if len(msg.encode("utf-8", errors="replace")) > max_inbound_bytes:
                    try:
                        ws.send("\r\n\x1b[31mInput too large.\x1b[0m\r\n")
                    except Exception:
                        pass
                    break
                text = msg

            last_io_at = time.monotonic()

            is_resize, rows, cols = _maybe_resize_json(text)
            if is_resize and rows is not None and cols is not None:
                try:
                    _set_winsize(master_fd, rows, cols)
                except OSError:
                    pass
                continue

            try:
                os.write(master_fd, text.encode("utf-8"))
            except OSError:
                break
    finally:
        stop.set()
        try:
            os.close(master_fd)
        except OSError:
            pass
        try:
            os.kill(pid, signal.SIGHUP)
        except ProcessLookupError:
            pass
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
        reader_thread.join(timeout=2.0)
        watchdog_thread.join(timeout=2.0)


def handle_terminal_ws_e2b(ws) -> None:
    """E2B sandbox-backed terminal session over WebSocket.

    Uses E2B's PTY API (interactive bash) and proxies bytes to/from the browser.
    """

    try:
        from e2b import PtySize, Sandbox  # type: ignore
    except Exception:
        try:
            ws.send(
                "\r\n\x1b[31mE2B terminal provider is not available. "
                "Install the 'e2b' Python package and set E2B_API_KEY.\x1b[0m\r\n"
            )
        except Exception:
            pass
        return

    send_lock = threading.Lock()
    last_io_at = time.monotonic()
    stop = threading.Event()

    def safe_ws_send(text: str) -> None:
        nonlocal last_io_at
        last_io_at = time.monotonic()
        try:
            with send_lock:
                ws.send(text)
        except Exception:
            stop.set()

    sandbox = None
    terminal = None
    terminal_pid: int | None = None
    reader_thread: threading.Thread | None = None

    # Limits (configurable)
    max_session_seconds = int(current_app.config["TERMINAL_MAX_SESSION_SECONDS"])
    idle_timeout_seconds = int(current_app.config["TERMINAL_IDLE_TIMEOUT_SECONDS"])
    max_inbound_bytes = int(current_app.config["TERMINAL_MAX_INBOUND_BYTES"])

    started_at = time.monotonic()

    def watchdog() -> None:
        while not stop.is_set():
            now = time.monotonic()
            if max_session_seconds > 0 and now - started_at > max_session_seconds:
                safe_ws_send("\r\n\x1b[31mTerminal session timed out.\x1b[0m\r\n")
                stop.set()
                return
            if idle_timeout_seconds > 0 and now - last_io_at > idle_timeout_seconds:
                safe_ws_send("\r\n\x1b[31mTerminal session idle timeout.\x1b[0m\r\n")
                stop.set()
                return
            time.sleep(1.0)

    watchdog_thread = threading.Thread(target=watchdog, name="e2b-tty-watchdog", daemon=True)

    try:
        template_name = str(current_app.config["E2B_TEMPLATE_NAME"] or "").strip()
        allow_internet = bool(current_app.config["E2B_ALLOW_INTERNET_ACCESS"])
        if template_name:
            sandbox = Sandbox.create(
                template=template_name,
                allow_internet_access=allow_internet,
            )
        else:
            sandbox = Sandbox.create(
                allow_internet_access=allow_internet,
            )

        try:
            session["e2b_terminal_sandbox_id"] = sandbox.sandbox_id
            _force_save_session(
                hypothesis_id="D",
                location="app/terminal_session.py:handle_terminal_ws_e2b",
            )
            print('handle_terminal_ws_e2b', sandbox.sandbox_id)
            print('handle_terminal_ws_e2b session', session.get("e2b_terminal_sandbox_id", ''))
        except Exception:
            pass

        terminal = sandbox.pty.create(
            PtySize(rows=24, cols=80),
            timeout=0,  # keep alive; we enforce our own caps above
        )
        terminal_pid = int(getattr(terminal, "pid", 0) or 0) or None

        def reader() -> None:
            if terminal is None:
                return
            try:
                for stdout, stderr, pty in terminal:
                    if stop.is_set():
                        break
                    if stdout is not None:
                        safe_ws_send(stdout)
                    elif stderr is not None:
                        safe_ws_send(stderr)
                    elif pty is not None:
                        safe_ws_send(pty.decode("utf-8", errors="replace"))
            except Exception:
                stop.set()

        reader_thread = threading.Thread(target=reader, name="e2b-pty-reader", daemon=True)
        reader_thread.start()

        # Start IPython if available in *this* PTY shell; otherwise fall back.
        # This avoids mismatches between commands.run() PATH vs interactive bash PATH.
        if terminal_pid is not None:
            sandbox.pty.send_stdin(terminal_pid, b"ipython\n")
        else:
            safe_ws_send(
                "\r\n\x1b[33mWarning: missing PTY pid; input may not work as expected.\x1b[0m\r\n"
            )

        watchdog_thread.start()

        while not stop.is_set():
            msg = ws.receive()
            if msg is None:
                break

            if isinstance(msg, bytes):
                if len(msg) > max_inbound_bytes:
                    safe_ws_send("\r\n\x1b[31mInput too large.\x1b[0m\r\n")
                    break
                text = msg.decode("utf-8", errors="replace")
            else:
                if len(msg.encode("utf-8", errors="replace")) > max_inbound_bytes:
                    safe_ws_send("\r\n\x1b[31mInput too large.\x1b[0m\r\n")
                    break
                text = msg

            last_io_at = time.monotonic()

            is_resize, rows, cols = _maybe_resize_json(text)
            if is_resize and rows is not None and cols is not None and terminal_pid is not None:
                try:
                    sandbox.pty.resize(terminal_pid, PtySize(rows=rows, cols=cols))
                except Exception:
                    pass
                continue

            if terminal_pid is None:
                continue

            try:
                sandbox.pty.send_stdin(terminal_pid, text.encode("utf-8"))
            except Exception:
                break
    finally:
        stop.set()
        try:
            if terminal is not None:
                try:
                    terminal.disconnect()
                except Exception:
                    pass
            if reader_thread is not None:
                reader_thread.join(timeout=2.0)
        finally:
            if sandbox is not None and terminal_pid is not None:
                try:
                    sandbox.pty.kill(terminal_pid)
                except Exception:
                    pass
            try:
                if session.get("e2b_terminal_sandbox_id") == getattr(sandbox, "sandbox_id", None):
                    session.pop("e2b_terminal_sandbox_id", None)
            except Exception:
                pass
            if sandbox is not None:
                # Close/free sandbox resources if supported by SDK version.
                close_fn: Callable[[], Any] | None = getattr(sandbox, "close", None)
                if callable(close_fn):
                    try:
                        close_fn()
                    except Exception:
                        pass
