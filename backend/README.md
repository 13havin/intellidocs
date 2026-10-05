# IntelliDocs Backend

FastAPI backend for IntelliDocs, a document and research workspace under active development. The API provides health and application metadata endpoints plus PostgreSQL-backed user creation and retrieval.

## Tech stack

- **FastAPI and Uvicorn** for the API and development server
- **Pydantic** for request and response validation, including email validation
- **PostgreSQL, SQLAlchemy, and psycopg2** for persistent storage and database sessions
- **Alembic** for database schema migrations
- **python-dotenv** for loading local environment configuration
- **pytest and HTTPX** for API tests through FastAPI's `TestClient`

## Local setup

You need Python with `pip` and `venv`, and a running PostgreSQL server. The repository does not currently pin Python or dependency versions.

From the repository root:

```sh
cd backend
python -m venv .venv
```

Activate the virtual environment:

**Windows PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```sh
source .venv/bin/activate
```

If your system uses `python3`, use `python3 -m venv .venv` when creating the environment. All remaining commands assume the environment is active and the working directory is `backend/`.

Install dependencies:

```sh
python -m pip install -r requirements.txt
```

### PostgreSQL configuration

Create a development database using pgAdmin or a PostgreSQL SQL session with a role allowed to create databases:

```sql
CREATE DATABASE intellidocs;
```

Create `backend/.env` with your connection details:

```dotenv
DATABASE_URL=postgresql+psycopg2://YOUR_USER:YOUR_PASSWORD@localhost:5432/intellidocs
```

Replace the placeholders with your PostgreSQL credentials. URL-encode reserved characters in credentials, such as `@` in a password. The database role needs permission to create and alter tables in the target schema.

`app/core/config.py` loads `.env` and reads `DATABASE_URL`. Both the application and Alembic use this setting. An existing shell environment variable takes precedence over `.env`. The `.env` file is ignored by Git; keep real credentials out of committed files.

Apply migrations before starting the application:

```sh
python -m alembic upgrade head
```

Alembic creates the tables inside an existing database; it does not create the PostgreSQL database itself. The initial migration creates `users` with an auto-generated bigint ID, required name and unique email, and a creation timestamp default. The application does not automatically create tables at startup.

### Start the API

```sh
python -m uvicorn app.main:app --reload
```

The API runs at <http://127.0.0.1:8000>. The `--reload` option is intended for local development.

## Database migrations

Run migration commands from `backend/`, with `DATABASE_URL` pointing to the intended database.

| Command | Purpose |
| --- | --- |
| `python -m alembic current` | Show the database's recorded revision |
| `python -m alembic history` | Show migration history |
| `python -m alembic upgrade head` | Apply all pending migrations |
| `python -m alembic downgrade -1` | Undo the latest applied migration |
| `python -m alembic check` | Check for model changes requiring a migration |

After changing a SQLAlchemy model:

```sh
python -m alembic revision --autogenerate -m "describe the schema change"
```

Review the generated file in `alembic/versions/`, including both `upgrade()` and `downgrade()`, then apply it:

```sh
python -m alembic upgrade head
```

Import new model modules in `alembic/env.py` so their tables are registered in `Base.metadata` for autogeneration.

If the database is at the second migration, `downgrade -1` returns it to the first. Downgrades can delete data when they remove columns or tables. Keep migration files in version control, including migrations you have rolled back.

Deleting a migration file does not remove its database changes. If a database already contains `users` but has no matching migration history, the initial migration will try to create the table again. Use a fresh database to test the initial migration, or reconcile the existing schema and migration history before upgrading. `stamp head` only updates the recorded revision; it does not create or repair tables.

## API

Documentation is available while the server is running:

- [Swagger UI](http://127.0.0.1:8000/docs)
- [ReDoc](http://127.0.0.1:8000/redoc)
- [OpenAPI schema](http://127.0.0.1:8000/openapi.json)

| Method | Endpoint | Description | Success status |
| --- | --- | --- | --- |
| `GET` | `/health/` | Returns `{"status": "healthy"}` | `200` |
| `GET` | `/api/v1/info/` | Returns application name and version | `200` |
| `POST` | `/api/v1/users/` | Saves a user in PostgreSQL | `201` |
| `GET` | `/api/v1/users/{user_id}` | Retrieves a saved user by ID | `200` |

Use the paths shown above to avoid redirects. The health endpoint is a basic application check, not a database connectivity check.

### Create and retrieve a user

Example using PowerShell:

```powershell
$user = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/users/" `
  -ContentType "application/json" `
  -Body '{"name":"Alex","email":"alex@example.com"}'

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/users/$($user.id)"
```

Example response (the database generates the ID):

```json
{
  "id": 1,
  "name": "Alex",
  "email": "alex@example.com"
}
```

Both request fields are required. An invalid email returns `422`, an already registered email returns `409`, and retrieval of a missing user returns `404`. Authentication is not implemented.

## Tests

Run from `backend/` with the virtual environment active. The tests use FastAPI's `TestClient`, so Uvicorn does not need to be running. PostgreSQL must be running with a dedicated test database:

```sql
CREATE DATABASE intellidocs_test_db;
```

Configure its URL in `backend/.env` or `backend/test.env`:

```dotenv
TEST_DATABASE_URL=postgresql+psycopg2://YOUR_USER:YOUR_PASSWORD@localhost:5432/intellidocs_test_db
```

Use actual credentials and keep the test database separate from development data. Configuration precedence is the shell's `TEST_DATABASE_URL`, then `backend/test.env`, then `backend/.env`. Only the `TEST_DATABASE_URL` key is read from these files by the fixtures; they do not fall back to the development `DATABASE_URL`. Keep credentials out of committed files (`.env` is ignored by Git).

```sh
python -m pytest -v
```

Pytest automatically discovers shared fixtures in `tests/conftest.py`. The fixtures select the test URL before importing the application, check database connectivity, and create missing model tables once per test session. Each test gets its own database session and outer transaction. SQLAlchemy savepoints allow application code to call `commit()` while teardown still rolls back the test's rows. The FastAPI `get_db` dependency is overridden during each client fixture and restored afterward.

The tests cover health and metadata responses, user creation and retrieval, duplicate email rejection, a missing user, and invalid email validation. Each user test creates its own required data, so individual tests and repeat runs work without manually resetting the database:

```sh
python -m pytest tests/test_users.py::test_user_creation_same_email -v
```

Fixtures leave existing rows and table definitions in place. PostgreSQL sequence increments are not rolled back, so generated IDs can have gaps. Table creation uses `Base.metadata.create_all()`; it does not alter existing tables or validate Alembic migration history. Test migrations separately against a fresh database using the migration commands above, with `DATABASE_URL` explicitly pointing to that database.

## Project structure

```text
backend/
|-- alembic/
|   |-- env.py             # Database connection and model metadata for migrations
|   |-- versions/          # Versioned upgrade and downgrade scripts
|   `-- script.py.mako     # Migration template
|-- alembic.ini            # Alembic configuration
|-- app/
|   |-- main.py            # FastAPI application and router registration
|   |-- dependencies.py    # Per-request database session lifecycle
|   |-- core/config.py     # Load DATABASE_URL from the environment / .env
|   |-- db/database.py     # SQLAlchemy engine, session factory, and Base
|   |-- models/user.py     # SQLAlchemy users table definition
|   |-- routers/           # Health, metadata, and user endpoints
|   |-- schemas/           # Pydantic request and response models
|   `-- services/          # User persistence logic
|-- tests/                 # pytest API tests and shared conftest.py fixtures
|-- .env                   # Local connection settings (not committed)
|-- requirements.txt       # Runtime and test dependencies
`-- README.md
```

## Planned capabilities

Workspaces, document management, search, authentication, and AI-powered document analysis remain planned capabilities.
