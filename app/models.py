"""Database models."""

from app import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    credential_version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
