"""Recipient authentication and content routes."""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, session, url_for
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash

from app import db
from app.models import User

bp = Blueprint("site", __name__)


def current_user() -> User | None:
    user_id = session.get("user_id")
    version = session.get("credential_version")
    if not isinstance(user_id, int) or not isinstance(version, int):
        return None

    user = db.session.get(User, user_id)
    if user is None or user.credential_version != version:
        session.clear()
        return None
    return user


@bp.get("/")
def index():
    return redirect(url_for("site.content" if current_user() else "site.login"))


@bp.get("/login")
def login():
    if current_user():
        return redirect(url_for("site.content"))
    return render_template("login.html")


@bp.post("/login")
def login_post():
    name = request.form.get("name", "").strip()
    password = request.form.get("password", "")
    user = db.session.execute(db.select(User).filter_by(name=name)).scalar_one_or_none()

    if user is None or not check_password_hash(user.password_hash, password):
        return render_template("login.html", error="Name or password is incorrect."), 401

    session.clear()
    session["user_id"] = user.id
    session["credential_version"] = user.credential_version
    session.permanent = False
    return redirect(url_for("site.content"))


@bp.get("/content")
def content():
    user = current_user()
    if user is None:
        return redirect(url_for("site.login"))
    response = render_template("content.html", user=user)
    return response


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("site.login"))


@bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db.session.rollback()
        return "unavailable\n", 503
    return "ok\n", 200


@bp.after_app_request
def prevent_private_caching(response):
    if request.path in ("/login", "/content"):
        response.headers["Cache-Control"] = "no-store"
    return response
