"""Import or update recipients from a UTF-8 CSV file."""

from __future__ import annotations

import argparse
import csv
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import TextIO

from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import User


class ImportErrorDetail(ValueError):
    """A CSV error safe to display without exposing row contents."""


def read_rows(stream: TextIO) -> list[tuple[str, str, str]]:
    reader = csv.DictReader(stream, strict=True)
    if reader.fieldnames:
        reader.fieldnames[0] = reader.fieldnames[0].lstrip("\ufeff")
    if reader.fieldnames != ["name", "password", "content"]:
        raise ImportErrorDetail("CSV header must be name,password,content")

    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    try:
        for row in reader:
            line = reader.line_num
            if None in row or any(row.get(column) is None for column in reader.fieldnames):
                raise ImportErrorDetail(f"CSV row ending at line {line} has the wrong number of fields")
            name = row["name"].strip()
            password = row["password"]
            content = row["content"]
            if not name or not password.strip() or not content.strip():
                raise ImportErrorDetail(f"CSV row ending at line {line} has a missing value")
            if len(name) > 120:
                raise ImportErrorDetail(f"CSV row ending at line {line} has a name over 120 characters")
            if name in seen:
                raise ImportErrorDetail(f"CSV row ending at line {line} repeats a name")
            seen.add(name)
            rows.append((name, password, content))
    except csv.Error as exc:
        raise ImportErrorDetail(f"Malformed CSV near line {reader.line_num}") from exc
    return rows


def import_rows(rows: list[tuple[str, str, str]]) -> tuple[int, int]:
    created = updated = 0
    with db.session.begin():
        for name, password, content in rows:
            user = db.session.execute(db.select(User).filter_by(name=name)).scalar_one_or_none()
            password_hash = generate_password_hash(password)
            if user is None:
                db.session.add(User(name=name, password_hash=password_hash, content=content))
                created += 1
            else:
                user.password_hash = password_hash
                user.content = content
                user.credential_version += 1
                updated += 1
    return created, updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="UTF-8 CSV path, or - to read standard input")
    args = parser.parse_args(argv)

    try:
        stream_context = (
            nullcontext(sys.stdin)
            if args.csv_path == "-"
            else Path(args.csv_path).open("r", encoding="utf-8-sig", newline="")
        )
        with stream_context as stream:
            rows = read_rows(stream)
        app = create_app()
        with app.app_context():
            created, updated = import_rows(rows)
    except (ImportErrorDetail, OSError, SQLAlchemyError, RuntimeError) as exc:
        if isinstance(exc, ImportErrorDetail):
            print(f"Import failed: {exc}", file=sys.stderr)
        else:
            print(f"Import failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    print(f"Imported {created} new and {updated} existing users.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
