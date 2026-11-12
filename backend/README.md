# IntelliDocs Backend

FastAPI backend for IntelliDocs, a document and research workspace under active development. The API provides health and application metadata endpoints plus PostgreSQL-backed registration, password-based login, authenticated profile retrieval, and workspace creation and retrieval.

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

Configuration requirements:

- `DATABASE_URL` must use `postgresql://` or `postgresql+psycopg2://` and include a host, username, and database name. A valid URL does not guarantee database connectivity.
- `SECRET_KEY` must contain at least 32 UTF-8 bytes. Use a randomly generated secret, such as the command above produces.
- `ALGORITHM` must be exactly `HS256`.

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

| Command                          | Purpose                                       |
| -------------------------------- | --------------------------------------------- |
| `python -m alembic current`      | Show the database's recorded revision         |
| `python -m alembic history`      | Show migration history                        |
| `python -m alembic upgrade head` | Apply all pending migrations                  |
| `python -m alembic downgrade -1` | Undo the latest applied migration             |
| `python -m alembic check`        | Check for model changes requiring a migration |

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

| Method  | Endpoint                                              | Description                                                                    | Success status |
| ------- | ----------------------------------------------------- | ------------------------------------------------------------------------------ | -------------- |
| `GET`   | `/health/`                                            | Basic application health check; does not check database connectivity           | `200`          |
| `GET`   | `/api/v1/info/`                                       | Application name and version                                                   | `200`          |
| `POST`  | `/auth/register`                                      | Register with a name, email, and password as JSON                              | `201`          |
| `POST`  | `/auth/login`                                         | Verify form credentials and return an access token                             | `200`          |
| `GET`   | `/api/v1/users/me`                                    | Return the profile identified by the bearer token                              | `200`          |
| `POST`  | `/api/v1/workspaces/`                                 | Create a workspace from a JSON name and assign the authenticated user as owner | `201`          |
| `GET`   | `/api/v1/workspaces/`                                 | List workspaces the authenticated user belongs to                              | `200`          |
| `GET`   | `/api/v1/workspaces/{workspace_id}`                   | Retrieve a workspace the authenticated user belongs to                         | `200`          |
| `GET`   | `/api/v1/workspaces/{workspace_id}/members`           | List members of a workspace the authenticated user belongs to                  | `200`          |
| `POST`  | `/api/v1/workspaces/{workspace_id}/members`           | Add a registered user by email; requires workspace owner role                  | `201`          |
| `PATCH` | `/api/v1/workspaces/{workspace_id}/members/{user_id}` | Change a member's role; requires owner role and preserves the last owner       | `200`          |

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

The JWT `sub` (subject) claim contains the user's database ID as a string. Token validation converts it to an integer, and `/me` retrieves the user by ID. After switching from email-based subjects, log in again to obtain a new token; old email-based tokens are rejected.

Registration requires all three fields: a name that is not empty or whitespace-only, a valid email address, and a password of at least 8 characters containing an uppercase letter, a lowercase letter, and a digit. A special character is not required. Invalid registration input returns `422`; an already registered email returns `409`.

Login returns `401` for an unknown email or incorrect password. `/me` returns `401` for a missing, invalid, or expired token, or a token whose user no longer exists. Access-token refresh, revocation, and password reset are not implemented.

### Workspaces

All workspace endpoints require `Authorization: Bearer <access_token>`. Using the token from the login example above:

```powershell
$headers = @{ Authorization = "Bearer $($token.access_token)" }

$workspace = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/workspaces/" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"name":"Research documents"}'

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/workspaces/" `
  -Headers $headers

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/workspaces/$($workspace.id)" `
  -Headers $headers
```

Creation requires a JSON body with a string `name`. Missing, null, non-string, empty, or whitespace-only names return `422`; passing only a query parameter does not satisfy the body requirement. The validator requires 1–255 characters after stripping surrounding whitespace; exactly 255 characters are allowed, and longer trimmed names return `422`.

Names are stored and returned with surrounding whitespace removed; internal spaces are preserved. A padded name with exactly 255 characters after trimming is accepted and stored within the database limit.

The creator is taken from the authenticated user and receives the `owner` role automatically. Clients cannot choose another creator or override this role. The workspace and owner membership are committed together; a membership failure rolls back workspace creation.

Create and get responses contain `id`, `name`, `created_at`, and `updated_at`, with timestamps serialized as ISO-formatted strings. Listing returns an array of these objects. Owners, editors, and viewers can retrieve workspaces they belong to; other users cannot access them.

Missing or invalid authentication returns `401`. Listing without any memberships returns `200` with an empty array (`[]`), including when other users have workspaces. Retrieving a missing workspace or one the user does not belong to returns `404` with `Workspace not found`.

### Workspace members

Owners can add an existing registered user by email with a role of `owner`, `editor`, or `viewer`. Multiple owners are supported. This adds membership immediately; it does not send an invitation or register a new user.

Using `$headers` and `$workspace` from the workspace example, after registering another user with the email below:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/workspaces/$($workspace.id)/members" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"email":"colleague@example.com","role":"editor"}'

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/workspaces/$($workspace.id)/members" `
  -Headers $headers
```

Adding returns one object containing `email`, `role`, and `joined_at` (an ISO-formatted timestamp). Listing returns an array of these objects, including the workspace's owners. All three roles can list members of their workspace.

| Condition                                                      | Status |
| -------------------------------------------------------------- | ------ |
| Missing or invalid authentication                              | `401`  |
| Workspace missing or requester is not a member                 | `404`  |
| Editor or viewer attempts to add a member                      | `403`  |
| Owner attempts to add an unregistered email                    | `404`  |
| Owner attempts to add an existing member, including themselves | `409`  |
| Missing email/role, invalid email, or unsupported role         | `422`  |

For a valid add request, the requester's membership and owner role are checked before looking up the target email. Listing also checks membership before returning member information. Member removal endpoints are not implemented yet.

### Updating member roles

Owners can change an existing member's role with `PATCH /api/v1/workspaces/{workspace_id}/members/{user_id}` and JSON such as `{"role":"viewer"}`. The path uses the target user's integer database ID, not the membership row ID. A successful update returns `200` with `email`, `role`, and `joined_at`. Setting the current role again returns the existing member with `200`, without issuing an update or committing the session. This applies to owners, editors, and viewers as targets; the requester must still be an owner. Membership timestamps remain unchanged.

The last owner cannot be demoted to editor or viewer: the API returns `409` with `Cannot remove the last owner of the workspace`, and their role remains unchanged. An owner may demote themselves if another owner exists in the same workspace. Owners in other workspaces do not satisfy this rule. The sole owner can still promote or change other members and retain their own owner role.

Missing authentication returns `401`; a missing workspace or requester who is not a member gets `404`. Editor/viewer requesters get `403` with `You do not have permission to change member roles in this workspace`, including when requesting the target's current role. A target who is not a workspace member gets `404`. Demoting the last owner returns `409`. Missing or invalid roles and non-integer user IDs return `422`.

### Concurrent membership changes

Both the add-member and role-update services lock the workspace row using `SELECT ... FOR UPDATE` before checking permissions and membership. Changes to the same workspace wait for the current transaction; changes to different workspaces do not contend for that workspace row lock. The role-update service checks for another owner while holding this lock, before changing the target role.

A same-role request also acquires the workspace lock, but returns without committing. Its lock remains held until the request's database session closes and ends the transaction. Callers using the service outside the HTTP request lifecycle must end or close their session themselves.

If two owners concurrently demote themselves, one succeeds and the other is rejected as the last remaining owner. An add request waiting behind a role change rechecks its requester's permissions after acquiring the lock; if that requester has been demoted, the add is rejected. Last-owner policy failures roll back and release the lock immediately.

When two owners add the same person concurrently, one succeeds and the other rechecks membership after acquiring the lock, returning `409`. When they add different people, both can succeed in sequence. The unique `(workspace_id, user_id)` database constraint remains in place.

Commit releases the lock on success. On failure, including permission or lookup errors after locking, the service rolls back to release the lock. If PostgreSQL reports uniqueness error `23505` for table `workspace_members` and constraint `workspace_members_workspace_id_user_id_key`, the service translates that `IntegrityError` into `ExistingMemberError`, preserving the original error as its cause. The router returns `409`, just as it does for duplicates detected by the initial membership check. This is a fallback for writers that bypass the locking convention; the unique constraint remains the final safeguard.

Other database errors, including primary-key, foreign-key, and role-check violations, propagate after rollback rather than being mislabeled as duplicate membership. The constraint name in the handler must match the database constraint; update the handler if a migration renames it. Future membership removal operations must follow the same workspace-locking convention and preserve the last owner. Last-owner protection is enforced by these service methods, not by a database constraint on direct writes.

### Swagger authorization

In `/docs`, register a user, then click **Authorize**. Enter the email in `username` and the password. Swagger calls `/auth/login` and attaches the returned token to protected requests, including `/api/v1/users/me`.

Calling `/auth/login` through **Try it out** displays a token but does not automatically authorize later Swagger requests. Use **Authorize** for that workflow. There is no separate `/auth/token` or `/auth/verify_token` endpoint.

### Troubleshooting bearer-token authentication

For a `401` response from `/api/v1/users/me`, check the response's `detail`:

- `Not authenticated`: the request is missing the `Authorization` header or uses a scheme other than `Bearer`. Send `Authorization: Bearer <access_token>`, or use **Authorize** in Swagger.
- `Could not verify credentials`: the bearer token failed validation, or its user no longer exists. Log in again and send the newly issued token. Tokens can fail validation because they are malformed, expired, signed with a different key, or contain an invalid subject.

Opening `/me` directly in the browser address bar does not attach the bearer token. Calling login alone does not create a browser session; each protected request must include the header.

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

The standard database fixture creates a unique `pytest_<uuid>` PostgreSQL schema and creates current model tables inside it. The database role must have permission to create schemas in the test database. ORM operations use that schema; existing tables and rows are left untouched. Tests using `db_session` receive a separate session and outer transaction, with savepoints allowing application commits to be rolled back. The FastAPI `get_db` dependency override is restored after each test. At session teardown, the temporary schema and its objects are dropped.

Concurrency tests instead create a separate `pytest_concurrency_<uuid>` schema per test and commit setup data so independent connections can see it. Worker threads each own a connection and session. The tests verify actual blocking with PostgreSQL's `pg_blocking_pids()`, use bounded waits, and drop their temporary schema afterward. They exercise service-level concurrency rather than concurrent HTTP requests.

The suite covers:

- Health and application metadata responses.
- Registration, required fields, invalid email, duplicate email, and stored password hashing.
- Login and authenticated profile retrieval, incorrect passwords, unknown emails, and missing login fields.
- Profile access with missing, malformed, expired, incorrectly signed tokens, invalid subjects, and unknown users.
- Profile and registration responses excluding password fields.
- Workspace creation from JSON, required and invalid names, 1- and 255-character boundaries (including Unicode), rejection of overlong names, persisted owner membership, and rollback on membership failure.
- Workspace authentication failures, membership-filtered listing, empty lists returning `200`, and retrieval by owners, editors, and viewers.
- Workspace and membership database constraints against both model-created and Alembic-created tables.
- Member listing, owner-only additions, payload validation, duplicate membership, and missing users or workspaces.
- Role updates, unchanged-role requests issuing no writes or commits, promotions, allowed self-demotion with another owner, and last-owner rejection returning `409` scoped to the workspace.
- Concurrent self-demotions preserving one owner, additions rechecking permissions after a demotion, and last-owner rejection releasing its lock.
- Non-members receiving `404`, non-owner members receiving `403` on additions, and complete member response fields.
- Concurrent additions of the same or different users, write-failure rollback unblocking a waiting request, and permission errors releasing locks before session closure.
- Real PostgreSQL constraint failures injected after the membership pre-check: duplicate membership translates to `ExistingMemberError` and HTTP `409`; unrelated integrity errors propagate, and rollback permits a subsequent successful write.

Run a focused test or a test module:

```sh
python -m pytest tests/test_auth.py::test_register_login_and_get_profile -v
python -m pytest tests/test_users.py -v
python -m pytest tests/test_workspaces.py -v
python -m pytest tests/test_workspace_members.py -v
python -m pytest tests/test_workspace_member_concurrency.py -v
```

Repeat runs do not require a manual database reset. API tests run against model-created tables. The workspace constraint tests also apply the Alembic migration chain in a separate temporary `pytest_migrations_<uuid>` schema and verify constraints there. The duplicate-email test does not simulate simultaneous requests. If pytest is forcibly terminated before teardown, its temporary schemas may remain.

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
|   |-- models/                # User, workspace, and workspace membership models
|   |-- routers/               # Auth, profile, workspace, health, and metadata endpoints
|   |-- schemas/
|   |   |-- auth.py            # Login, token response, and token data schemas
|   |   |-- users.py           # Registration input and safe profile response
|   |   |-- workspaces.py      # Workspace name validation and response schemas
|   |   |-- workspace_members.py # Member email, role, and response schemas
|   |   `-- info.py            # Application metadata response
|   `-- services/
|       |-- auth_service.py    # Registration, credential verification, token issuance
|       |-- user_service.py    # User insertion and flush; receives a password hash
|       |-- workspace_service.py # Workspace creation and membership-filtered queries
|       |-- workspace_members_service.py # Member access checks and locked additions
|       `-- exceptions.py      # Application errors such as duplicate email
|-- tests/
|   |-- conftest.py            # Test configuration, isolated schema, rollback fixtures
|   |-- test_auth.py           # Registration, login, and full authentication flow
|   |-- test_users.py          # Protected-profile authentication failures
|   |-- test_workspaces.py     # Workspace API validation, access, and persistence
|   |-- test_workspace_constraints.py # Model and migration database constraints
|   |-- test_workspace_members.py # Member API permissions, responses, and validation
|   |-- test_workspace_member_concurrency.py # PostgreSQL locking across connections
|   |-- test_health.py
|   `-- test_info.py
|-- .env                       # Local settings (not committed)
|-- requirements.txt
`-- README.md
```

Routes handle request parsing and HTTP responses. The auth service coordinates password hashing, user creation, and registration commit/rollback; the user service inserts and flushes without committing. Token validation raises token errors, which the authenticated-user dependency translates into HTTP `401` responses.

## Planned capabilities

Document management, search, and AI-powered document analysis remain planned capabilities.
