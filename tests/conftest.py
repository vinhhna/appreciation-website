"""PostgreSQL-backed fixtures for the application tests."""

from __future__ import annotations

import os

import pytest
from flask_migrate import upgrade
from sqlalchemy.engine import make_url
from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import User


@pytest.fixture(scope="session")
def app():
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("Set TEST_DATABASE_URL to a dedicated PostgreSQL database named appreciation_site_test")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or url.database != "appreciation_site_test":
        pytest.fail("TEST_DATABASE_URL must point to PostgreSQL database appreciation_site_test")

    app = create_app(
        {
            "DATABASE_URL": database_url,
            "SECRET_KEY": "test-only-secret-key",
            "TESTING": True,
            "SESSION_COOKIE_SECURE": False,
        }
    )
    with app.app_context():
        upgrade()
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture(autouse=True)
def clean_users(app):
    with app.app_context():
        db.session.query(User).delete()
        db.session.commit()
    yield
    with app.app_context():
        db.session.remove()
        db.session.query(User).delete()
        db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def add_user(app):
    def add(name: str, password: str, content: str) -> User:
        with app.app_context():
            user = User(name=name, password_hash=generate_password_hash(password), content=content)
            db.session.add(user)
            db.session.commit()
            return user

    return add
