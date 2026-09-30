"""CSV parsing and transactional import tests."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from werkzeug.security import check_password_hash

from app import db
from app.models import User
from scripts.import_users import ImportErrorDetail, import_rows, main, read_rows


def test_create_update_and_hash_passwords(app):
    rows = read_rows(StringIO('name,password,content\nAlice,first-secret,"Hello, Alice\nThank you"\n'))
    with app.app_context():
        assert import_rows(rows) == (1, 0)
        user = db.session.execute(db.select(User).filter_by(name="Alice")).scalar_one()
        assert user.password_hash != "first-secret"
        assert check_password_hash(user.password_hash, "first-secret")
        assert user.content == "Hello, Alice\nThank you"

        db.session.remove()
        assert import_rows([("Alice", "second-secret", "Updated")]) == (0, 1)
        user = db.session.execute(db.select(User).filter_by(name="Alice")).scalar_one()
        db.session.refresh(user)
        assert user.credential_version == 2
        assert check_password_hash(user.password_hash, "second-secret")
        assert not check_password_hash(user.password_hash, "first-secret")


@pytest.mark.parametrize(
    "csv_text",
    [
        "name,password\nAlice,secret\n",
        "name,password,content\nAlice,secret,hello\nAlice,second,again\n",
        "name,password,content\nAlice,,hello\n",
        "name,password,content\nAlice,secret\n",
        "name,password,content\nAlice,secret,hello,extra\n",
    ],
)
def test_invalid_csv_is_rejected_before_writing(app, csv_text):
    with pytest.raises(ImportErrorDetail):
        read_rows(StringIO(csv_text))
    with app.app_context():
        assert db.session.execute(db.select(User)).scalars().all() == []


def test_import_is_atomic_when_a_later_row_fails(app):
    def hash_or_fail(password):
        if password == "fail":
            raise RuntimeError("hash failed")
        return "hash-for-test"

    with app.app_context():
        with patch("scripts.import_users.generate_password_hash", side_effect=hash_or_fail):
            with pytest.raises(RuntimeError):
                import_rows([("Alice", "good", "One"), ("Bob", "fail", "Two")])
        assert db.session.execute(db.select(User)).scalars().all() == []


def test_stdin_dash_interface(app, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", app.config["SQLALCHEMY_DATABASE_URI"])
    monkeypatch.setenv("SECRET_KEY", "test-only-secret-key")
    monkeypatch.setattr("sys.stdin", StringIO("name,password,content\nAlice,secret,Hello\n"))
    assert main(["-"]) == 0
    assert "Imported 1 new" in capsys.readouterr().out
    with app.app_context():
        assert db.session.execute(db.select(User)).scalar_one().name == "Alice"


def test_csv_path_interface(app, monkeypatch, tmp_path):
    csv_path = tmp_path / "users.csv"
    csv_path.write_text("\ufeffname,password,content\nAlice,secret,Hello\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", app.config["SQLALCHEMY_DATABASE_URI"])
    monkeypatch.setenv("SECRET_KEY", "test-only-secret-key")
    assert main([str(csv_path)]) == 0
    with app.app_context():
        assert db.session.execute(db.select(User)).scalar_one().name == "Alice"
