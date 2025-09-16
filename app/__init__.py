"""Application factory for the GreenCommerce ERP MVP."""
from flask import Flask

from app import database


def create_app() -> Flask:
    """Create the Flask application and initialize database tables."""
    app = Flask(__name__)
    app.config.setdefault("DATABASE", database.DATABASE_PATH)

    database.initialize_database()

    return app


__all__ = ["create_app"]
