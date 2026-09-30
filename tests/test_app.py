"""Recipient authentication and privacy tests."""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError

from app import create_app, db
from app.models import User
from scripts.import_users import import_rows


def csrf_token(client, path="/login"):
    html = client.get(path).get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def sign_in(client, name, password):
    token = csrf_token(client)
    return client.post("/login", data={"name": name, "password": password, "csrf_token": token})


def test_login_and_content_are_isolated(app, client, add_user):
    add_user("Alice", "alice-secret", "Alice's private message")
    add_user("Bob", "bob-secret", "Bob's private message")

    assert client.get("/content").status_code == 302
    assert client.get("/content/Bob").status_code == 404
    assert sign_in(client, " Alice ", "alice-secret").status_code == 302

    page = client.get("/content?name=Bob")
    assert page.status_code == 200
    assert "Alice&#39;s private message" in page.get_data(as_text=True)
    assert "Bob's private message" not in page.get_data(as_text=True)
    assert page.headers["Cache-Control"] == "no-store"


def test_wrong_credentials_share_a_generic_error(client, add_user):
    add_user("Alice", "correct", "Private")
    for name, password in (("Alice", "wrong"), ("Nobody", "wrong")):
        response = sign_in(client, name, password)
        assert response.status_code == 401
        assert "Name or password is incorrect." in response.get_data(as_text=True)
        assert client.get("/content").status_code == 302


def test_content_is_escaped_and_logout_clears_session(client, add_user):
    add_user("Alice", "secret", "Hello\n<script>alert('x')</script>")
    sign_in(client, "Alice", "secret")
    page = client.get("/content").get_data(as_text=True)
    assert "<script>" not in page
    assert "&lt;script&gt;" in page

    token = csrf_token(client, "/content")
    assert client.post("/logout", data={"csrf_token": token}).status_code == 302
    assert client.get("/content").status_code == 302


def test_post_routes_require_csrf(client, add_user):
    add_user("Alice", "secret", "Private")
    assert client.post("/login", data={"name": "Alice", "password": "secret"}).status_code == 400
    sign_in(client, "Alice", "secret")
    assert client.post("/logout").status_code == 400
    assert client.get("/content").status_code == 200


def test_password_update_invalidates_existing_session(app, client, add_user):
    add_user("Alice", "old-secret", "Old message")
    sign_in(client, "Alice", "old-secret")

    with app.app_context():
        created, updated = import_rows([("Alice", "new-secret", "New message")])
        user = db.session.execute(db.select(User).filter_by(name="Alice")).scalar_one()
        assert (created, updated) == (0, 1)
        assert user.credential_version == 2

    assert client.get("/content").status_code == 302
    assert sign_in(client, "Alice", "old-secret").status_code == 401
    assert sign_in(client, "Alice", "new-secret").status_code == 302
    assert "New message" in client.get("/content").get_data(as_text=True)


def test_health_checks_postgresql(client):
    assert client.get("/health").status_code == 200
    error = OperationalError("SELECT 1", {}, Exception("connection failed"))
    with patch.object(db.session, "execute", side_effect=error):
        response = client.get("/health")
    assert response.status_code == 503
    assert "connection failed" not in response.get_data(as_text=True)


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app({"SECRET_KEY": "test-key"})


def test_sqlite_is_rejected():
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        create_app({"DATABASE_URL": "sqlite:///site.db", "SECRET_KEY": "test-key"})
