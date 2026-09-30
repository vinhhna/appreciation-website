# Personal appreciation site

A small Flask site that shows each invited recipient only their own plain text message. It uses PostgreSQL for accounts and content, Werkzeug for password hashing, and Flask-Migrate/Alembic for schema changes.

## Project layout

- `app/`: Flask app, SQLAlchemy model, routes, Jinja templates, and CSS
- `scripts/import_users.py`: administrator-only CSV importer
- `migrations/`: committed Alembic migrations
- `tests/`: PostgreSQL-backed tests
- `wsgi.py`: Gunicorn and Flask CLI entry point

## Local setup

Use Python 3.12 (also selected for Railway through `.python-version`) and a dedicated PostgreSQL database. For example, in PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:APP_ENV = "development"
$env:DATABASE_URL = "postgresql://app_user:password@localhost:5432/appreciation_site"
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
flask --app wsgi:app db upgrade
flask --app wsgi:app run
```

`DATABASE_URL` and `SECRET_KEY` are required. The app fails at startup without either one. Only PostgreSQL is supported; there is no SQLite fallback. Never commit actual environment values.

## Import recipients

Make a UTF-8 CSV with the exact header `name,password,content`:

```csv
name,password,content
Alice,replace-with-a-strong-unique-password,"Thank you, Alice.
I appreciate you."
```

Run `python -m scripts.import_users users.csv` or pipe CSV data to `python -m scripts.import_users -`. Each import is atomic. Existing names receive a new password hash and content; their previous sessions are invalidated. Names not in the file remain unchanged. Names are case-sensitive after surrounding whitespace is removed. Passwords and content retain their CSV text.

The CSV contains plaintext passwords before import. Keep it outside Git, restrict access, and remove it when no longer needed. The importer never prints passwords or content, and PostgreSQL stores only password hashes.

## Tests

Set `TEST_DATABASE_URL` to an isolated PostgreSQL database named `appreciation_site_test`, then run `pytest`. The test suite migrates that database and deletes its `users` rows between tests; do not point it at a database containing real data.

## Railway deployment

1. Push this source to a **private GitHub repository**, without `.env` or CSV files. Create a Railway project with one service from that repository and one PostgreSQL service. Keep PostgreSQL private.
2. On the web service, set `DATABASE_URL` to `${{Postgres.DATABASE_URL}}` using a Railway reference variable, set a long random `SECRET_KEY`, and set `APP_ENV=production`.
3. Set the **pre-deploy command** to `flask --app wsgi:app db upgrade` and the **start command** to `gunicorn --workers 1 --bind 0.0.0.0:$PORT wsgi:app`. Railpack builds the Python dependencies from `requirements.txt`.
4. Set the health check path to `/health`, then generate a public domain for the web service. `/health` returns 200 only while PostgreSQL is reachable; otherwise it returns 503.

The initial deployment uses one Gunicorn service with one worker. It needs no Redis or background jobs. Railway can deploy new commits from the linked GitHub branch automatically.

To import into production while keeping PostgreSQL private, link the Railway CLI to the web service and stream the CSV through SSH. In PowerShell:

```powershell
Get-Content -Raw -Encoding UTF8 .\users.csv | railway ssh -- python -m scripts.import_users -
```

On macOS or Linux:

```sh
cat users.csv | railway ssh -- python -m scripts.import_users -
```

The Railway CLI must be installed and signed in. The CSV is sent to the importer through standard input; it is not committed or copied into the deployment image.
