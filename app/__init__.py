from flask import Flask


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    from . import routes

    app.register_blueprint(routes.bp)

    return app
