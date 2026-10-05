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

The tests use FastAPI's `TestClient`, so a running Uvicorn server is not required. PostgreSQL must be running, and the target database must have migrations applied. Tests use the application's `DATABASE_URL`; there is no automatic test database override or transaction rollback fixture. A file named `test.env` is not automatically loaded.

Create a dedicated test database using pgAdmin or a PostgreSQL SQL session:

```sql
CREATE DATABASE intellidocs_test;
```

Point your shell to this database before running Alembic or pytest. Substitute your actual connection details.

**Windows PowerShell**

```powershell
$env:DATABASE_URL = "postgresql+psycopg2://YOUR_USER:YOUR_PASSWORD@localhost:5432/intellidocs_test"
python -m alembic upgrade head
python -m pytest -v
```

**macOS / Linux**

```sh
export DATABASE_URL='postgresql+psycopg2://YOUR_USER:YOUR_PASSWORD@localhost:5432/intellidocs_test'
python -m alembic upgrade head
python -m pytest -v
```

Coverage includes health and metadata responses, user creation and retrieval, duplicate email rejection, a missing user, and invalid email validation.

### Repeat test runs

The current user tests commit `test@ex.com` and do not clean it up. The duplicate-email test depends on the creation test running first, and the missing-user test assumes ID `9999` does not exist. Run the full suite against a fresh test database; isolated or parallel user test runs are not currently independent.

Before repeating the suite, reset the dedicated test database schema. **These commands drop migration-managed tables and their data. Confirm `DATABASE_URL` points to the disposable test database first.**

```sh
python -m alembic downgrade base
python -m alembic upgrade head
python -m pytest -v
```

After testing, remove the shell override to use `.env` again for newly started commands:

```powershell
# Windows PowerShell
Remove-Item Env:DATABASE_URL
```

```sh
# macOS / Linux
unset DATABASE_URL
```

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
|-- tests/                 # pytest API tests
|-- .env                   # Local connection settings (not committed)
|-- requirements.txt       # Runtime and test dependencies
`-- README.md
```

## Planned capabilities

Workspaces, document management, search, authentication, and AI-powered document analysis remain planned capabilities.
