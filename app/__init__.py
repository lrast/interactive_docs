from flask import Flask


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    from . import chat, routes, terminal_ws

    app.register_blueprint(routes.bp)
    app.register_blueprint(chat.bp)
    terminal_ws.register_terminal_ws(app)

    return app
