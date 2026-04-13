from flask import Flask


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    from . import chat, routes

    app.register_blueprint(routes.bp)
    app.register_blueprint(chat.bp)

    return app
