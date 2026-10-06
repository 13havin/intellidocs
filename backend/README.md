# IntelliDocs Backend

FastAPI backend for IntelliDocs, a document and research workspace under active development. The API provides health and application metadata endpoints plus PostgreSQL-backed registration, password-based login, and authenticated profile retrieval.

## Tech stack

- **FastAPI and Uvicorn** for the API and development server
- **Pydantic** for request and response validation, including email validation
- **PostgreSQL, SQLAlchemy, and psycopg2** for persistent storage and database sessions
- **pwdlib with Argon2** for password hashing and verification
- **PyJWT** for signed access tokens and **python-multipart** for login form parsing
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
SECRET_KEY=REPLACE_WITH_A_RANDOM_SECRET
ALGORITHM=HS256
```

Replace the placeholders with your PostgreSQL credentials. URL-encode reserved characters in credentials, such as `@` in a password. The database role needs permission to create and alter tables in the target schema.

Generate a signing secret locally and copy it into `SECRET_KEY`:

```sh
python -c "import secrets; print(secrets.token_hex(32))"
```

`app/core/config.py` loads `.env` and reads `DATABASE_URL`, `SECRET_KEY`, and `ALGORITHM`. Set all three before using authentication. The signing secret must stay private and consistent across application instances. Both the application and Alembic use `DATABASE_URL`. An existing shell environment variable takes precedence over `.env`. The `.env` file is ignored by Git; keep real credentials out of committed files.

Apply migrations before starting the application:

```sh
python -m alembic upgrade head
```

Alembic creates the tables inside an existing database; it does not create the PostgreSQL database itself. The initial migration creates `users` with an auto-generated bigint ID, required name and unique email, and a creation timestamp default. The later password migration adds the column that stores password hashes. The application does not automatically create tables at startup.

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
| `GET` | `/health/` | Basic application health check; does not check database connectivity | `200` |
| `GET` | `/api/v1/info/` | Application name and version | `200` |
| `POST` | `/auth/register` | Register with a name, email, and password as JSON | `201` |
| `POST` | `/auth/login` | Verify form credentials and return an access token | `200` |
| `GET` | `/api/v1/users/me` | Return the profile identified by the bearer token | `200` |

### Register, login, and retrieve your profile

Example using PowerShell with demonstration credentials:

```powershell
$user = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/auth/register" `
  -ContentType "application/json" `
  -Body '{"name":"Alex","email":"alex@example.com","password":"Example-password-123!"}'

$token = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/auth/login" `
  -ContentType "application/x-www-form-urlencoded" `
  -Body @{ username = "alex@example.com"; password = "Example-password-123!" }

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/users/me" `
  -Headers @{ Authorization = "Bearer $($token.access_token)" }
```

Registration accepts JSON. Login accepts form data with fields named `username` and `password`; put the email address in `username`. Login returns:

```json
{
  "access_token": "<signed JWT>",
  "token_type": "Bearer"
}
```

Login tokens expire after 30 minutes. Send `Authorization: Bearer <access_token>` with each protected request. Login does not set a session cookie. Registration and `/me` return only `id`, `name`, and `email`; passwords are hashed with Argon2 before storage and are not included in those responses.

Registration requires all three fields and returns `422` for invalid input or `409` for an already registered email. Login returns `401` for an unknown email or incorrect password. `/me` returns `401` for a missing, invalid, or expired token, or a token whose user no longer exists. Access-token refresh, revocation, and password reset are not implemented.

### Swagger authorization

In `/docs`, register a user, then click **Authorize**. Enter the email in `username` and the password. Swagger calls `/auth/login` and attaches the returned token to protected requests, including `/api/v1/users/me`.

Calling `/auth/login` through **Try it out** displays a token but does not automatically authorize later Swagger requests. Use **Authorize** for that workflow. There is no separate `/auth/token` or `/auth/verify_token` endpoint.

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

Pytest automatically discovers shared fixtures in `tests/conftest.py`. Before importing the application, fixtures select `TEST_DATABASE_URL` and set a test-only JWT signing key and `HS256` algorithm. Tests do not use the application's real signing secret.

Each test session creates a unique `pytest_<uuid>` PostgreSQL schema and creates current model tables inside it. The database role must have permission to create schemas in the test database. ORM operations use that schema; existing tables and rows are left untouched. Each test receives a separate session and outer transaction, with savepoints allowing application commits to be rolled back. The FastAPI `get_db` dependency override is restored after each test. At session teardown, the temporary schema and its objects are dropped.

The suite covers:

- Health and application metadata responses.
- Registration, required fields, invalid email, duplicate email, and stored password hashing.
- Login and authenticated profile retrieval, incorrect passwords, unknown emails, and missing login fields.
- Profile access with missing, malformed, expired, incorrectly signed tokens, invalid subjects, and unknown users.
- Profile and registration responses excluding password fields.

Run a focused test or a test module:

```sh
python -m pytest tests/test_auth.py::test_register_login_and_get_profile -v
python -m pytest tests/test_users.py -v
```

Repeat runs do not require a manual database reset. These are API tests against model-created tables: they do not apply or validate Alembic migrations, and the duplicate-email test does not simulate simultaneous requests. Validate migrations separately against a fresh database with `DATABASE_URL` pointing to it. If pytest is forcibly terminated before teardown, its temporary schema may remain.

## Project structure

```text
backend/
|-- alembic/
|   |-- env.py                 # Migration connection and model metadata
|   |-- versions/              # Versioned upgrade and downgrade scripts
|   `-- script.py.mako         # Migration template
|-- alembic.ini
|-- app/
|   |-- main.py                # Application and router registration
|   |-- dependencies.py        # Database session and authenticated-user dependencies
|   |-- core/
|   |   |-- config.py          # Database and JWT environment settings
|   |   |-- security.py        # Password hashing and verification
|   |   `-- tokens.py          # JWT creation/validation and OAuth2 bearer scheme
|   |-- db/database.py         # SQLAlchemy engine, session factory, and Base
|   |-- models/user.py         # Database user model
|   |-- routers/               # Auth, profile, health, and metadata HTTP endpoints
|   |-- schemas/
|   |   |-- auth.py            # Login, token response, and token data schemas
|   |   |-- users.py           # Registration input and safe profile response
|   |   `-- info.py            # Application metadata response
|   `-- services/
|       |-- auth_service.py    # Registration, credential verification, token issuance
|       |-- user_service.py    # User insertion and flush; receives a password hash
|       `-- exceptions.py      # Application errors such as duplicate email
|-- tests/
|   |-- conftest.py            # Test configuration, isolated schema, rollback fixtures
|   |-- test_auth.py           # Registration, login, and full authentication flow
|   |-- test_users.py          # Protected-profile authentication failures
|   |-- test_health.py
|   `-- test_info.py
|-- .env                       # Local settings (not committed)
|-- requirements.txt
`-- README.md
```

Routes handle request parsing and HTTP responses. The auth service coordinates password hashing, user creation, and registration commit/rollback; the user service inserts and flushes without committing. Token validation raises token errors, which the authenticated-user dependency translates into HTTP `401` responses.

## Planned capabilities

Workspaces, document management, search, and AI-powered document analysis remain planned capabilities.
