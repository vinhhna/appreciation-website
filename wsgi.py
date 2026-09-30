"""WSGI entry point for Gunicorn and Flask CLI."""

from app import create_app

app = create_app()
