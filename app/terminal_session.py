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

if sys.platform != "win32":
    import fcntl
    import pty
    import termios


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

    try:
        _set_winsize(master_fd, 24, 80)
    except OSError:
        pass

    reader_thread.start()

    try:
        while True:
            msg = ws.receive()
            if msg is None:
                break
            if isinstance(msg, bytes):
                text = msg.decode("utf-8", errors="replace")
            else:
                text = msg

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
