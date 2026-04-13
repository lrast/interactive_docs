from flask_sock import Sock

from .terminal_session import handle_terminal_ws


def register_terminal_ws(app) -> Sock:
    sock = Sock(app)

    @sock.route("/ws/terminal")
    def terminal(ws):
        handle_terminal_ws(ws)

    return sock
