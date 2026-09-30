"""Application setup for the appreciation site."""

from __future__ import annotations

import os

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()


def create_app(test_config: dict | None = None) -> Flask:
    """Create the web app with an explicit PostgreSQL connection."""
    config = test_config or {}
    database_url = config.get("DATABASE_URL", os.environ.get("DATABASE_URL"))
    secret_key = config.get("SECRET_KEY", os.environ.get("SECRET_KEY"))

    if not database_url:
        raise RuntimeError("DATABASE_URL must be set to a PostgreSQL connection URL")
    if not secret_key:
        raise RuntimeError("SECRET_KEY must be set")

    try:
        url = make_url(database_url)
    except ArgumentError:
        raise RuntimeError("DATABASE_URL is not a valid PostgreSQL URL") from None
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("DATABASE_URL must point to PostgreSQL")
    if "SQLALCHEMY_DATABASE_URI" in config:
        raise RuntimeError("Configure PostgreSQL through DATABASE_URL only")

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=url.set(drivername="postgresql+psycopg").render_as_string(
            hide_password=False
        ),
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_SECURE=os.environ.get("APP_ENV", "production") != "development",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    app.config.update({key: value for key, value in config.items() if key != "DATABASE_URL"})

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from app import models  # noqa: F401 - register the model for migrations
    from app.routes import bp

    app.register_blueprint(bp)
    return app
